"""Run BUY/SELL/HOLD label generation."""

from __future__ import annotations

import logging
import sys

import psycopg2

from src.config import (
    LABEL_BUY_THRESHOLD,
    LABEL_LOOKAHEAD_ROWS,
    LABEL_SELL_THRESHOLD,
    postgres_dsn,
)
from src.processing.labels import label_distribution, process_all_symbols

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info(
        "Starting label generation | lookahead=%s rows buy>=%s%% sell<=%s%%",
        LABEL_LOOKAHEAD_ROWS,
        LABEL_BUY_THRESHOLD,
        LABEL_SELL_THRESHOLD,
    )

    results = process_all_symbols()
    total = sum(results.values())

    for symbol, count in results.items():
        logger.info("  %s: %s rows", symbol, count)

    if total == 0:
        logger.warning("No labels created. Run feature engineering first.")
        sys.exit(1)

    with psycopg2.connect(postgres_dsn()) as conn:
        distribution = label_distribution(conn)

    logger.info("Done. Total labeled rows: %s", total)
    logger.info(
        "Label distribution: BUY=%s SELL=%s HOLD=%s",
        distribution.get("BUY", 0),
        distribution.get("SELL", 0),
        distribution.get("HOLD", 0),
    )


if __name__ == "__main__":
    main()
