from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import RealDictCursor

from src.api.deps import get_db
from src.api.schemas import ModelRunOut

router = APIRouter(prefix="/api/v1/models", tags=["models"])


def _to_model_run(row: dict[str, Any]) -> ModelRunOut:
    metrics = row["metrics"]
    if isinstance(metrics, str):
        metrics = json.loads(metrics)
    macro = metrics.get("macro_f1")
    macro_f1 = float(macro) if macro is not None else None
    return ModelRunOut(
        id=row["id"],
        model_path=row["model_path"],
        macro_f1=macro_f1,
        metrics=metrics,
        trained_at=row["trained_at"],
    )


@router.get("", response_model=list[ModelRunOut])
def list_model_runs(
    limit: int = Query(default=20, ge=1, le=100),
    db: PgConnection = Depends(get_db),
) -> list[ModelRunOut]:
    query = """
        SELECT id, model_path, metrics, trained_at
        FROM model_runs
        ORDER BY trained_at DESC
        LIMIT %s
    """
    with db.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, (limit,))
        rows = cur.fetchall()
    return [_to_model_run(row) for row in rows]


@router.get("/latest", response_model=ModelRunOut)
def latest_model_run(db: PgConnection = Depends(get_db)) -> ModelRunOut:
    query = """
        SELECT id, model_path, metrics, trained_at
        FROM model_runs
        ORDER BY trained_at DESC
        LIMIT 1
    """
    with db.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query)
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="no model runs found")
    return _to_model_run(row)


@router.get("/{run_id}", response_model=ModelRunOut)
def get_model_run(
    run_id: int,
    db: PgConnection = Depends(get_db),
) -> ModelRunOut:
    query = """
        SELECT id, model_path, metrics, trained_at
        FROM model_runs
        WHERE id = %s
    """
    with db.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, (run_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="model run not found")
    return _to_model_run(row)
