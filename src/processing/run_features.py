"""Run feature engineering on processed_features."""

from __future__ import annotations

import logging
import sys

from src.config import MIN_ROWS_FOR_FEATURES
from src.processing.features import process_all_symbols

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Starting feature engineering...")
    results = process_all_symbols()
    total = sum(results.values())

    for symbol, count in results.items():
        logger.info("  %s: %s rows", symbol, count)

    logger.info("Done. Total rows upserted: %s", total)
    if total == 0:
        logger.warning(
            "No features written. Ensure ingestion is running and each symbol has "
            "at least %s market_events rows.",
            MIN_ROWS_FOR_FEATURES,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
