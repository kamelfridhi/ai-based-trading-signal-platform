from __future__ import annotations

from fastapi import APIRouter, Depends
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import RealDictCursor

from src.api.deps import get_db
from src.api.schemas import SymbolOut

router = APIRouter(prefix="/api/v1/symbols", tags=["symbols"])


@router.get("", response_model=list[SymbolOut])
def list_symbols(db: PgConnection = Depends(get_db)) -> list[SymbolOut]:
    with db.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT symbol FROM symbols ORDER BY symbol")
        rows = cur.fetchall()
    return [SymbolOut(**row) for row in rows]
