from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from psycopg2.extensions import connection as PgConnection

from src.api.deps import get_db
from src.api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(db: PgConnection = Depends(get_db)) -> HealthResponse:
    try:
        with db.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return HealthResponse(status="ok", database="ok")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc
