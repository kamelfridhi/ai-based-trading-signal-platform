"""Run inference and persist trading_signals above confidence threshold."""

from __future__ import annotations

import argparse
import logging
import sys

from src.ml.predict import run_inference

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model-run-id",
        type=int,
        default=None,
        help="Use a specific model_runs id (default: latest).",
    )
    args = parser.parse_args()

    try:
        count = run_inference(model_run_id=args.model_run_id)
    except ValueError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    if count == 0:
        sys.exit(2)


if __name__ == "__main__":
    main()
