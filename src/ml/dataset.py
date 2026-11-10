"""Load training data and build symbol-wise sequence windows."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import psycopg2
from sklearn.preprocessing import StandardScaler

from src.config import (
    INDEX_TO_LABEL,
    LABEL_TO_INDEX,
    ML_TRAIN_RATIO,
    ML_WINDOW_SIZE,
    SYMBOLS,
    postgres_dsn,
)
from src.processing.labels import FEATURE_COLUMNS


@dataclass
class SequenceBatch:
    """Training or inference tensors plus metadata."""

    x: np.ndarray
    symbol_ids: np.ndarray
    y: np.ndarray | None
    symbols: list[str]
    timestamps: list[pd.Timestamp]


@dataclass
class DataSplit:
    train: SequenceBatch
    test: SequenceBatch
    scaler: StandardScaler
    symbol_to_id: dict[str, int]
    split_timestamp: pd.Timestamp


def _load_training_frame(conn: psycopg2.extensions.connection) -> pd.DataFrame:
    cols = ", ".join(["symbol", "timestamp", "label"] + FEATURE_COLUMNS)
    query = f"""
        SELECT {cols}
        FROM ml_training_data
        ORDER BY timestamp ASC
    """
    return pd.read_sql(query, conn)


def _load_features_frame(conn: psycopg2.extensions.connection) -> pd.DataFrame:
    cols = ", ".join(["symbol", "timestamp"] + FEATURE_COLUMNS)
    query = f"""
        SELECT {cols}
        FROM processed_features
        ORDER BY timestamp ASC
    """
    return pd.read_sql(query, conn)


def _symbol_id_map(symbols: list[str]) -> dict[str, int]:
    ordered = sorted(set(symbols))
    return {sym: idx for idx, sym in enumerate(ordered)}


def _windowize(
    df: pd.DataFrame,
    window: int,
    symbol_to_id: dict[str, int],
    with_labels: bool,
) -> SequenceBatch:
    x_list: list[np.ndarray] = []
    sym_ids: list[int] = []
    y_list: list[int] = []
    symbols: list[str] = []
    timestamps: list[pd.Timestamp] = []

    for symbol, group in df.groupby("symbol", sort=False):
        group = group.sort_values("timestamp").reset_index(drop=True)
        sid = symbol_to_id.get(symbol)
        if sid is None:
            continue

        values = group[FEATURE_COLUMNS].astype(float).to_numpy()
        ts = pd.to_datetime(group["timestamp"], utc=True)

        if with_labels:
            labels = group["label"].map(LABEL_TO_INDEX).to_numpy()

        for end in range(window - 1, len(group)):
            start = end - window + 1
            window_values = values[start : end + 1]
            if np.isnan(window_values).any():
                continue

            x_list.append(window_values)
            sym_ids.append(sid)
            symbols.append(symbol)
            timestamps.append(ts.iloc[end])

            if with_labels:
                y_list.append(int(labels[end]))

    x = np.asarray(x_list, dtype=np.float32)
    symbol_ids = np.asarray(sym_ids, dtype=np.int64)
    y = np.asarray(y_list, dtype=np.int64) if with_labels else None

    return SequenceBatch(x=x, symbol_ids=symbol_ids, y=y, symbols=symbols, timestamps=timestamps)


def _scale_sequences(
    x: np.ndarray,
    scaler: StandardScaler | None,
    fit: bool,
) -> tuple[np.ndarray, StandardScaler]:
    n, w, f = x.shape
    flat = x.reshape(n * w, f)
    if fit:
        scaler = StandardScaler()
        scaled = scaler.fit_transform(flat)
    else:
        if scaler is None:
            raise ValueError("scaler is required when fit=False")
        scaled = scaler.transform(flat)
    return scaled.reshape(n, w, f).astype(np.float32), scaler  # type: ignore[return-value]


def build_train_test_split() -> DataSplit:
    with psycopg2.connect(postgres_dsn()) as conn:
        df = _load_training_frame(conn)

    if df.empty:
        raise ValueError("ml_training_data is empty — run label generation first.")

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    symbol_to_id = _symbol_id_map(SYMBOLS)

    full = _windowize(df, ML_WINDOW_SIZE, symbol_to_id, with_labels=True)
    if full.y is None or len(full.x) == 0:
        raise ValueError(
            f"Not enough rows to build windows (need window size {ML_WINDOW_SIZE})."
        )

    ts_array = np.array(full.timestamps)
    order = np.argsort(ts_array)
    split_idx = int(len(order) * ML_TRAIN_RATIO)
    if split_idx <= 0 or split_idx >= len(order):
        raise ValueError("Train/test split failed — increase data or adjust ML_TRAIN_RATIO.")

    train_idx = order[:split_idx]
    test_idx = order[split_idx:]
    split_timestamp = full.timestamps[order[split_idx]]

    train_x = full.x[train_idx]
    test_x = full.x[test_idx]
    train_scaled, scaler = _scale_sequences(train_x, None, fit=True)
    test_scaled, _ = _scale_sequences(test_x, scaler, fit=False)

    train = SequenceBatch(
        x=train_scaled,
        symbol_ids=full.symbol_ids[train_idx],
        y=full.y[train_idx],
        symbols=[full.symbols[i] for i in train_idx],
        timestamps=[full.timestamps[i] for i in train_idx],
    )
    test = SequenceBatch(
        x=test_scaled,
        symbol_ids=full.symbol_ids[test_idx],
        y=full.y[test_idx],
        symbols=[full.symbols[i] for i in test_idx],
        timestamps=[full.timestamps[i] for i in test_idx],
    )

    return DataSplit(
        train=train,
        test=test,
        scaler=scaler,
        symbol_to_id=symbol_to_id,
        split_timestamp=split_timestamp,
    )


def build_latest_windows(scaler: StandardScaler, symbol_to_id: dict[str, int]) -> SequenceBatch:
    """One latest window per symbol from processed_features."""
    with psycopg2.connect(postgres_dsn()) as conn:
        df = _load_features_frame(conn)

    if df.empty:
        raise ValueError("processed_features is empty.")

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    x_list: list[np.ndarray] = []
    sym_ids: list[int] = []
    symbols: list[str] = []
    timestamps: list[pd.Timestamp] = []

    for symbol in SYMBOLS:
        group = df[df["symbol"] == symbol].sort_values("timestamp").reset_index(drop=True)
        if len(group) < ML_WINDOW_SIZE:
            continue

        values_block = group[FEATURE_COLUMNS].astype(float).to_numpy()
        end_idx: int | None = None
        for end in range(len(group) - 1, ML_WINDOW_SIZE - 2, -1):
            start = end - ML_WINDOW_SIZE + 1
            window = values_block[start : end + 1]
            if not np.isnan(window).any():
                end_idx = end
                break

        if end_idx is None:
            continue

        start = end_idx - ML_WINDOW_SIZE + 1
        values = values_block[start : end_idx + 1]
        sid = symbol_to_id.get(symbol)
        if sid is None:
            continue

        x_list.append(values)
        sym_ids.append(sid)
        symbols.append(symbol)
        timestamps.append(
            pd.to_datetime(group["timestamp"].iloc[end_idx], utc=True)
        )

    if not x_list:
        raise ValueError("No symbol has enough rows for inference windows.")

    x = np.asarray(x_list, dtype=np.float32)
    scaled, _ = _scale_sequences(x, scaler, fit=False)

    return SequenceBatch(
        x=scaled,
        symbol_ids=np.asarray(sym_ids, dtype=np.int64),
        y=None,
        symbols=symbols,
        timestamps=timestamps,
    )


def decode_label(index: int) -> str:
    return INDEX_TO_LABEL[index]


def build_latest_window_for_symbol(
    symbol: str,
    scaler: StandardScaler,
    symbol_to_id: dict[str, int],
) -> tuple[np.ndarray, int, pd.Timestamp]:
    """Return scaled window (1, W, F), symbol_id, and as-of timestamp."""
    symbol = symbol.strip().upper()
    if symbol not in symbol_to_id:
        raise ValueError(f"Unknown symbol '{symbol}'. Tracked: {', '.join(SYMBOLS)}")

    with psycopg2.connect(postgres_dsn()) as conn:
        cols = ", ".join(["symbol", "timestamp"] + FEATURE_COLUMNS)
        query = f"""
            SELECT {cols}
            FROM processed_features
            WHERE symbol = %s
            ORDER BY timestamp ASC
        """
        group = pd.read_sql(query, conn, params=(symbol,))

    if len(group) < ML_WINDOW_SIZE:
        raise ValueError(
            f"Not enough feature rows for {symbol} "
            f"(need {ML_WINDOW_SIZE}, have {len(group)})."
        )

    group["timestamp"] = pd.to_datetime(group["timestamp"], utc=True)
    values_block = group[FEATURE_COLUMNS].astype(float).to_numpy()

    end_idx: int | None = None
    for end in range(len(group) - 1, ML_WINDOW_SIZE - 2, -1):
        start = end - ML_WINDOW_SIZE + 1
        window = values_block[start : end + 1]
        if not np.isnan(window).any():
            end_idx = end
            break

    if end_idx is None:
        raise ValueError(
            f"No complete {ML_WINDOW_SIZE}-row window for {symbol} "
            "(missing indicators or sentiment)."
        )

    start = end_idx - ML_WINDOW_SIZE + 1
    values = values_block[start : end_idx + 1]
    x = np.asarray([values], dtype=np.float32)
    scaled, _ = _scale_sequences(x, scaler, fit=False)
    ts = pd.to_datetime(group["timestamp"].iloc[end_idx], utc=True)
    return scaled, symbol_to_id[symbol], ts
