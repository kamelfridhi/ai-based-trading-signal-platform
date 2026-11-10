"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import analytics, health, models, pipeline, prices, signals, symbols
from src.config import API_CORS_ORIGINS

app = FastAPI(
    title="Trading Signal Platform API",
    version="1.1.0",
    description="Read trading signals and trigger ML pipeline jobs.",
)


@app.get("/api/v1/version")
def api_version() -> dict[str, object]:
    return {
        "version": "1.1.0",
        "features": ["analytics", "signals", "models", "pipeline", "prices"],
    }

app.add_middleware(
    CORSMiddleware,
    allow_origins=API_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(analytics.router)
app.include_router(signals.router)
app.include_router(models.router)
app.include_router(symbols.router)
app.include_router(prices.router)
app.include_router(pipeline.router)
