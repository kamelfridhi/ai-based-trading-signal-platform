"""On-demand prediction and analytics for a single symbol."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import psycopg2
import torch
from psycopg2.extras import RealDictCursor

from src.config import (
    INDEX_TO_LABEL,
    ML_SIGNAL_CONFIDENCE,
    SYMBOLS,
    postgres_dsn,
)
from src.ml.dataset import build_latest_window_for_symbol
from src.ml.predict import _load_model, _load_run_path, _restore_scaler


def _normalize_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if s not in SYMBOLS:
        raise ValueError(f"Symbol '{symbol}' is not tracked. Valid: {', '.join(SYMBOLS)}")
    return s


def _feature_row(conn: psycopg2.extensions.connection, symbol: str, as_of: datetime) -> dict[str, Any]:
    query = """
        SELECT timestamp, close, volume,
               return_1, return_5, return_15,
               sma_10, sma_20, rsi_14,
               macd, macd_signal, volume_change_pct,
               news_count_1h, news_sentiment_avg_1h
        FROM processed_features
        WHERE symbol = %s AND timestamp = %s
        LIMIT 1
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, (symbol, as_of))
        row = cur.fetchone()
    if not row:
        query_latest = """
            SELECT timestamp, close, volume,
                   return_1, return_5, return_15,
                   sma_10, sma_20, rsi_14,
                   macd, macd_signal, volume_change_pct,
                   news_count_1h, news_sentiment_avg_1h
            FROM processed_features
            WHERE symbol = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query_latest, (symbol,))
            row = cur.fetchone()
    if not row:
        return {}
    out: dict[str, Any] = dict(row)
    for key in (
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
        "news_sentiment_avg_1h",
    ):
        if out.get(key) is not None:
            out[key] = float(out[key])
    if out.get("news_count_1h") is not None:
        out["news_count_1h"] = int(out["news_count_1h"])
    return out


def _recent_news(conn: psycopg2.extensions.connection, symbol: str, limit: int = 5) -> list[dict[str, Any]]:
    query = """
        SELECT title, sentiment_label, sentiment_value::float, published_at
        FROM market_news
        WHERE symbol = %s AND sentiment_label IS NOT NULL
        ORDER BY published_at DESC
        LIMIT %s
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, (symbol, limit))
        return list(cur.fetchall())


def _latest_price(conn: psycopg2.extensions.connection, symbol: str) -> dict[str, Any] | None:
    query = """
        SELECT close::float, timestamp
        FROM market_events
        WHERE symbol = %s
        ORDER BY timestamp DESC
        LIMIT 1
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, (symbol,))
        return cur.fetchone()


@torch.no_grad()
def analyze_symbol(
    symbol: str,
    model_run_id: int | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    """Run model inference and attach technical + news context."""
    sym = _normalize_symbol(symbol)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    run_id, path = _load_run_path(model_run_id)
    model, blob = _load_model(path, device)
    scaler = _restore_scaler(blob)
    symbol_to_id: dict[str, int] = blob["symbol_to_id"]

    window, sym_id, as_of = build_latest_window_for_symbol(sym, scaler, symbol_to_id)
    x = torch.tensor(window, dtype=torch.float32).to(device)
    sid = torch.tensor([sym_id], dtype=torch.long).to(device)
    logits = model(x, sid)
    probs = torch.softmax(logits, dim=-1).cpu().numpy()[0]

    label_idx = int(probs.argmax())
    confidence = float(probs[label_idx])
    predicted = INDEX_TO_LABEL[label_idx]
    as_of_dt = as_of.to_pydatetime()
    meets = confidence >= ML_SIGNAL_CONFIDENCE

    with psycopg2.connect(postgres_dsn()) as conn:
        features = _feature_row(conn, sym, as_of_dt)
        price = _latest_price(conn, sym)
        news = _recent_news(conn, sym)

        if persist and meets:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trading_signals (
                        model_run_id, symbol, timestamp, predicted_label,
                        prob_buy, prob_sell, prob_hold, confidence
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (model_run_id, symbol, timestamp) DO UPDATE SET
                        predicted_label = EXCLUDED.predicted_label,
                        prob_buy = EXCLUDED.prob_buy,
                        prob_sell = EXCLUDED.prob_sell,
                        prob_hold = EXCLUDED.prob_hold,
                        confidence = EXCLUDED.confidence,
                        created_at = NOW()
                    """,
                    (
                        run_id,
                        sym,
                        as_of_dt,
                        predicted,
                        float(probs[0]),
                        float(probs[1]),
                        float(probs[2]),
                        confidence,
                    ),
                )
            conn.commit()

    return {
        "symbol": sym,
        "as_of": as_of_dt.isoformat(),
        "price": price,
        "prediction": {
            "predicted_label": predicted,
            "confidence": confidence,
            "prob_buy": float(probs[0]),
            "prob_sell": float(probs[1]),
            "prob_hold": float(probs[2]),
            "meets_threshold": meets,
            "confidence_threshold": ML_SIGNAL_CONFIDENCE,
            "model_run_id": run_id,
        },
        "technicals": {
            k: features.get(k)
            for k in (
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
            )
            if features
        },
        "sentiment": {
            "news_count_1h": features.get("news_count_1h") if features else None,
            "news_sentiment_avg_1h": features.get("news_sentiment_avg_1h") if features else None,
        },
        "recent_news": news,
        "persisted_signal": bool(persist and meets),
    }
