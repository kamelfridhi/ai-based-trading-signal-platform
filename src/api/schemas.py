"""Pydantic response and request models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

SignalLabel = Literal["BUY", "SELL", "HOLD"]
JobStatus = Literal["queued", "running", "completed", "failed"]
PipelineJobType = Literal["train", "predict"]


class HealthResponse(BaseModel):
    status: str
    database: str


class TradingSignalOut(BaseModel):
    id: int
    model_run_id: int
    symbol: str
    timestamp: datetime
    predicted_label: SignalLabel
    prob_buy: float
    prob_sell: float
    prob_hold: float
    confidence: float
    created_at: datetime


class ModelRunOut(BaseModel):
    id: int
    model_path: str
    macro_f1: float | None
    metrics: dict[str, Any]
    trained_at: datetime


class SymbolOut(BaseModel):
    symbol: str


class LatestPriceOut(BaseModel):
    symbol: str
    close: float
    timestamp: datetime


class PredictRequest(BaseModel):
    model_run_id: int | None = Field(
        default=None, description="Defaults to latest model run."
    )


class PipelineJobOut(BaseModel):
    job_id: str
    job_type: PipelineJobType
    status: JobStatus


class PipelineJobDetail(PipelineJobOut):
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
