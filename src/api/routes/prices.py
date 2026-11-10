from __future__ import annotations

from fastapi import APIRouter, Depends
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import RealDictCursor

from src.api.deps import get_db
from src.api.schemas import LatestPriceOut

router = APIRouter(prefix="/api/v1/prices", tags=["prices"])


@router.get("/latest", response_model=list[LatestPriceOut])
def latest_prices(db: PgConnection = Depends(get_db)) -> list[LatestPriceOut]:
    query = """
        SELECT DISTINCT ON (symbol)
               symbol, close::float AS close, timestamp
        FROM market_events
        ORDER BY symbol, timestamp DESC
    """
    with db.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query)
        rows = cur.fetchall()
    return [LatestPriceOut(**row) for row in rows]
