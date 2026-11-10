"""Train the sequence classifier and register a model run."""

from __future__ import annotations

import logging
import sys

from src.ml.train import train_model

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    try:
        run_id, path, metrics = train_model()
    except ValueError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    logger.info(
        "Training complete | model_run_id=%s macro_f1=%.4f | %s",
        run_id,
        metrics.get("macro_f1", 0),
        path,
    )
    logger.info("Next: python -m src.ml.run_predict")


if __name__ == "__main__":
    main()
