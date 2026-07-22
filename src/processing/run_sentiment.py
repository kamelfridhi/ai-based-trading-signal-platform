"""Run FinBERT sentiment scoring on market news."""

from __future__ import annotations

import logging
import sys

from src.processing.sentiment import process_all_news

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Starting news sentiment analysis...")
    count = process_all_news()
    if count == 0:
        logger.warning("No news was scored. Check that market_news has rows.")
        sys.exit(1)

    logger.info("Done. Re-run feature engineering to refresh sentiment averages:")
    logger.info("  python -m src.processing.run_features")


if __name__ == "__main__":
    main()
