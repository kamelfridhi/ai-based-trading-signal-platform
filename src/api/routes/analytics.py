from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.ml.symbol_insight import analyze_symbol

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


class AnalyzeRequest(BaseModel):
    symbol: str = Field(..., min_length=1, examples=["AAPL", "BTC-USD"])
    model_run_id: int | None = None
    persist: bool = False


def _analyze(
    symbol: str,
    model_run_id: int | None,
    persist: bool,
) -> dict:
    try:
        return analyze_symbol(symbol, model_run_id=model_run_id, persist=persist)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/lookup")
def symbol_analytics_post(body: AnalyzeRequest) -> dict:
    return _analyze(body.symbol, body.model_run_id, body.persist)


@router.get("/{symbol}")
def symbol_analytics(
    symbol: str,
    model_run_id: int | None = None,
    persist: bool = Query(
        default=False,
        description="Save to trading_signals when confidence >= threshold.",
    ),
) -> dict:
    return _analyze(symbol, model_run_id, persist)
