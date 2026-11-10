from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import RealDictCursor

from src.api.deps import get_db
from src.api.schemas import SignalLabel, TradingSignalOut

router = APIRouter(prefix="/api/v1/signals", tags=["signals"])

_SIGNAL_ROW = """
    SELECT id, model_run_id, symbol, timestamp, predicted_label,
           prob_buy::float, prob_sell::float, prob_hold::float,
           confidence::float, created_at
    FROM trading_signals
"""


def _rows_to_signals(rows: list[dict]) -> list[TradingSignalOut]:
    return [TradingSignalOut(**row) for row in rows]


@router.get("", response_model=list[TradingSignalOut])
def list_signals(
    symbol: str | None = None,
    label: SignalLabel | None = None,
    min_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    limit: int = Query(default=50, ge=1, le=200),
    db: PgConnection = Depends(get_db),
) -> list[TradingSignalOut]:
    clauses: list[str] = []
    params: list[object] = []

    if symbol:
        clauses.append("symbol = %s")
        params.append(symbol)
    if label:
        clauses.append("predicted_label = %s")
        params.append(label)
    if min_confidence is not None:
        clauses.append("confidence >= %s")
        params.append(min_confidence)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"{_SIGNAL_ROW} {where} ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    with db.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    return _rows_to_signals(rows)


@router.get("/latest", response_model=list[TradingSignalOut])
def latest_signals_per_symbol(
    db: PgConnection = Depends(get_db),
) -> list[TradingSignalOut]:
    query = f"""
        SELECT DISTINCT ON (symbol)
               id, model_run_id, symbol, timestamp, predicted_label,
               prob_buy::float, prob_sell::float, prob_hold::float,
               confidence::float, created_at
        FROM trading_signals
        ORDER BY symbol, created_at DESC
    """
    with db.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query)
        rows = cur.fetchall()
    return _rows_to_signals(rows)


@router.get("/{signal_id}", response_model=TradingSignalOut)
def get_signal(
    signal_id: int,
    db: PgConnection = Depends(get_db),
) -> TradingSignalOut:
    query = f"{_SIGNAL_ROW} WHERE id = %s"
    with db.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, (signal_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="signal not found")
    return TradingSignalOut(**row)
