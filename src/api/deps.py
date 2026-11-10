"""Database dependency for FastAPI routes."""

from __future__ import annotations

from collections.abc import Generator

import psycopg2
from psycopg2.extensions import connection as PgConnection

from src.config import postgres_dsn


def get_db() -> Generator[PgConnection, None, None]:
    conn = psycopg2.connect(postgres_dsn())
    try:
        yield conn
    finally:
        conn.close()
