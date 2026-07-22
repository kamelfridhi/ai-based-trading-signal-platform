"""Generate BUY/SELL/HOLD labels from future price returns."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from src.config import (
    LABEL_BUY_THRESHOLD,
    LABEL_LOOKAHEAD_ROWS,
    LABEL_SELL_THRESHOLD,
    SYMBOLS,
    postgres_dsn,
)

logger = logging.getLogger(__name__)

FEATURE_COLUMNS = [
    "close",
    "volume",
    "return_1",
    "return_5",
    "return_15",
    "sma_10",
    "sma_20",
    "rsi_14",
    "macd",
    "macd_signal",
    "volume_change_pct",
    "news_count_1h",
    "news_sentiment_avg_1h",
]

UPSERT_SQL = """
INSERT INTO ml_training_data (
    symbol, timestamp, close, volume,
    return_1, return_5, return_15,
    sma_10, sma_20, rsi_14,
    macd, macd_signal, volume_change_pct,
    news_count_1h, news_sentiment_avg_1h,
    future_close, future_return_pct, label
) VALUES %s
ON CONFLICT (symbol, timestamp) DO UPDATE SET
    close = EXCLUDED.close,
    volume = EXCLUDED.volume,
    return_1 = EXCLUDED.return_1,
    return_5 = EXCLUDED.return_5,
    return_15 = EXCLUDED.return_15,
    sma_10 = EXCLUDED.sma_10,
    sma_20 = EXCLUDED.sma_20,
    rsi_14 = EXCLUDED.rsi_14,
    macd = EXCLUDED.macd,
    macd_signal = EXCLUDED.macd_signal,
    volume_change_pct = EXCLUDED.volume_change_pct,
    news_count_1h = EXCLUDED.news_count_1h,
    news_sentiment_avg_1h = EXCLUDED.news_sentiment_avg_1h,
    future_close = EXCLUDED.future_close,
    future_return_pct = EXCLUDED.future_return_pct,
    label = EXCLUDED.label,
    labeled_at = NOW()
"""


def assign_label(future_return_pct: float) -> str:
    if future_return_pct >= LABEL_BUY_THRESHOLD:
        return "BUY"
    if future_return_pct <= LABEL_SELL_THRESHOLD:
        return "SELL"
    return "HOLD"


def _load_features(conn: psycopg2.extensions.connection, symbol: str) -> pd.DataFrame:
    query = """
        SELECT symbol, timestamp, close, volume,
               return_1, return_5, return_15,
               sma_10, sma_20, rsi_14,
               macd, macd_signal, volume_change_pct,
               news_count_1h, news_sentiment_avg_1h
        FROM processed_features
        WHERE symbol = %s
        ORDER BY timestamp ASC
    """
    return pd.read_sql(query, conn, params=(symbol,))


def _build_labeled_frame(features: pd.DataFrame) -> pd.DataFrame:
    if features.empty:
        return features

    df = features.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["future_close"] = df["close"].shift(-LABEL_LOOKAHEAD_ROWS)
    df["future_return_pct"] = ((df["future_close"] - df["close"]) / df["close"]) * 100
    df = df.dropna(subset=["future_close"])
    df["label"] = df["future_return_pct"].apply(assign_label)
    return df


def _num(value: Any) -> float | None:
    if pd.isna(value):
        return None
    return float(value)


def _row_to_tuple(row: pd.Series) -> tuple[Any, ...]:
    ts = pd.Timestamp(row["timestamp"]).tz_convert("UTC").to_pydatetime()
    return (
        row["symbol"],
        ts,
        _num(row["close"]),
        _num(row["volume"]),
        _num(row["return_1"]),
        _num(row["return_5"]),
        _num(row["return_15"]),
        _num(row["sma_10"]),
        _num(row["sma_20"]),
        _num(row["rsi_14"]),
        _num(row["macd"]),
        _num(row["macd_signal"]),
        _num(row["volume_change_pct"]),
        int(row["news_count_1h"]),
        _num(row["news_sentiment_avg_1h"]),
        _num(row["future_close"]),
        _num(row["future_return_pct"]),
        row["label"],
    )


def process_symbol(conn: psycopg2.extensions.connection, symbol: str) -> int:
    features = _load_features(conn, symbol)
    if features.empty:
        logger.warning("No processed features for %s — skipping.", symbol)
        return 0

    labeled = _build_labeled_frame(features)
    if labeled.empty:
        logger.warning(
            "Not enough feature rows for %s after %s-row lookahead.",
            symbol,
            LABEL_LOOKAHEAD_ROWS,
        )
        return 0

    rows = [_row_to_tuple(row) for _, row in labeled.iterrows()]
    with conn.cursor() as cur:
        execute_values(cur, UPSERT_SQL, rows, page_size=500)
    conn.commit()

    label_counts = labeled["label"].value_counts().to_dict()
    logger.info("Labeled %s rows for %s — %s", len(rows), symbol, label_counts)
    return len(rows)


def process_all_symbols(symbols: list[str] | None = None) -> dict[str, int]:
    target_symbols = symbols or SYMBOLS
    results: dict[str, int] = {}

    with psycopg2.connect(postgres_dsn()) as conn:
        for symbol in target_symbols:
            try:
                results[symbol] = process_symbol(conn, symbol)
            except Exception as exc:
                conn.rollback()
                logger.error("Failed to label %s: %s", symbol, exc)
                results[symbol] = 0

    return results


def label_distribution(conn: psycopg2.extensions.connection) -> dict[str, int]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT label, COUNT(*)
            FROM ml_training_data
            GROUP BY label
            ORDER BY label
            """
        )
        return {row[0]: row[1] for row in cur.fetchall()}
