"""Load bronze data, compute features, and write to processed_features."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from src.config import MIN_ROWS_FOR_FEATURES, SYMBOLS, postgres_dsn
from src.processing.indicators import build_feature_frame

logger = logging.getLogger(__name__)

UPSERT_SQL = """
INSERT INTO processed_features (
    symbol, timestamp, close, volume,
    return_1, return_5, return_15,
    sma_10, sma_20, rsi_14,
    macd, macd_signal, volume_change_pct,
    news_count_1h, news_sentiment_avg_1h
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
    processed_at = NOW()
"""


def _load_market_events(conn: psycopg2.extensions.connection, symbol: str) -> pd.DataFrame:
    query = """
        SELECT DISTINCT ON (symbol, timestamp)
            symbol, timestamp, close, volume
        FROM market_events
        WHERE symbol = %s
        ORDER BY symbol, timestamp ASC, id DESC
    """
    return pd.read_sql(query, conn, params=(symbol,))


def _load_news(conn: psycopg2.extensions.connection, symbol: str) -> pd.DataFrame:
    query = """
        SELECT published_at, sentiment_value
        FROM market_news
        WHERE symbol = %s
        ORDER BY published_at ASC
    """
    df = pd.read_sql(query, conn, params=(symbol,))
    if not df.empty:
        df["published_at"] = pd.to_datetime(df["published_at"], utc=True)
    return df


def _attach_news_context(features: pd.DataFrame, news: pd.DataFrame) -> pd.DataFrame:
    if news.empty:
        features["news_count_1h"] = 0
        features["news_sentiment_avg_1h"] = None
        return features

    timestamps = pd.to_datetime(features["timestamp"], utc=True)
    counts: list[int] = []
    averages: list[float | None] = []
    published = news["published_at"]

    for ts in timestamps:
        window_start = ts - timedelta(hours=1)
        mask = (published >= window_start) & (published <= ts)
        counts.append(int(mask.sum()))
        window_values = news.loc[mask, "sentiment_value"].dropna()
        averages.append(float(window_values.mean()) if not window_values.empty else None)

    features["news_count_1h"] = counts
    features["news_sentiment_avg_1h"] = averages
    return features


def _row_to_tuple(row: pd.Series) -> tuple[Any, ...]:
    def _num(value: Any) -> float | None:
        if pd.isna(value):
            return None
        return float(value)

    ts = pd.Timestamp(row["timestamp"])
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")

    return (
        row["symbol"],
        ts.to_pydatetime(),
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
    )


def process_symbol(conn: psycopg2.extensions.connection, symbol: str) -> int:
    """Compute and upsert features for one symbol. Returns rows written."""
    ohlcv = _load_market_events(conn, symbol)
    if ohlcv.empty:
        logger.warning("No market events for %s — skipping.", symbol)
        return 0

    if len(ohlcv) < MIN_ROWS_FOR_FEATURES:
        logger.warning(
            "Not enough rows for %s (%s/%s) — need more ingestion first.",
            symbol,
            len(ohlcv),
            MIN_ROWS_FOR_FEATURES,
        )
        return 0

    ohlcv["timestamp"] = pd.to_datetime(ohlcv["timestamp"], utc=True)
    features = build_feature_frame(ohlcv)
    features = _attach_news_context(features, _load_news(conn, symbol))
    features = features.drop_duplicates(subset=["symbol", "timestamp"], keep="last")

    rows = [_row_to_tuple(row) for _, row in features.iterrows()]
    with conn.cursor() as cur:
        execute_values(cur, UPSERT_SQL, rows, page_size=500)
    conn.commit()

    logger.info("Processed %s rows for %s", len(rows), symbol)
    return len(rows)


def process_all_symbols(symbols: list[str] | None = None) -> dict[str, int]:
    """Process all configured symbols. Returns symbol -> rows written."""
    target_symbols = symbols or SYMBOLS
    results: dict[str, int] = {}

    with psycopg2.connect(postgres_dsn()) as conn:
        for symbol in target_symbols:
            try:
                results[symbol] = process_symbol(conn, symbol)
            except Exception as exc:
                conn.rollback()
                logger.error("Failed to process %s: %s", symbol, exc)
                results[symbol] = 0

    return results
