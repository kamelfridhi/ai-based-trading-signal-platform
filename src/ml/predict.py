"""Load checkpoint and write trading_signals (confidence >= threshold)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import psycopg2
import torch
from sklearn.preprocessing import StandardScaler

from src.config import (
    INDEX_TO_LABEL,
    ML_SIGNAL_CONFIDENCE,
    postgres_dsn,
)
from src.ml.dataset import build_latest_windows
from src.ml.model import TemporalAttentionClassifier
from src.processing.labels import FEATURE_COLUMNS

logger = logging.getLogger(__name__)

NUM_FEATURES = len(FEATURE_COLUMNS)


def _load_run_path(model_run_id: int | None) -> tuple[int, Path]:
    with psycopg2.connect(postgres_dsn()) as conn:
        with conn.cursor() as cur:
            if model_run_id is not None:
                cur.execute(
                    "SELECT id, model_path FROM model_runs WHERE id = %s",
                    (model_run_id,),
                )
            else:
                cur.execute(
                    "SELECT id, model_path FROM model_runs ORDER BY trained_at DESC LIMIT 1"
                )
            row = cur.fetchone()
            if not row:
                raise ValueError("No model_runs found — train a model first.")
            return int(row[0]), Path(row[1])


def _restore_scaler(blob: dict[str, Any]) -> StandardScaler:
    scaler = StandardScaler()
    scaler.mean_ = np.asarray(blob["scaler_mean"], dtype=np.float64)
    scaler.scale_ = np.asarray(blob["scaler_scale"], dtype=np.float64)
    scaler.n_features_in_ = len(scaler.mean_)
    return scaler


def _load_model(path: Path, device: torch.device) -> tuple[TemporalAttentionClassifier, dict[str, Any]]:
    blob = torch.load(path, map_location=device, weights_only=False)
    model = TemporalAttentionClassifier(
        num_features=blob["num_features"],
        num_symbols=blob["num_symbols"],
        symbol_embed_dim=blob["hyperparams"]["symbol_embed_dim"],
        hidden_size=blob["hyperparams"]["hidden_size"],
        num_layers=blob["hyperparams"]["num_layers"],
        num_classes=blob["num_classes"],
        dropout=blob["hyperparams"]["dropout"],
    ).to(device)
    model.load_state_dict(blob["model_state"])
    model.eval()
    return model, blob


@torch.no_grad()
def run_inference(model_run_id: int | None = None) -> int:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    run_id, path = _load_run_path(model_run_id)
    model, blob = _load_model(path, device)

    scaler = _restore_scaler(blob)
    symbol_to_id: dict[str, int] = blob["symbol_to_id"]
    batch = build_latest_windows(scaler, symbol_to_id)

    x = torch.tensor(batch.x, dtype=torch.float32).to(device)
    sym = torch.tensor(batch.symbol_ids, dtype=torch.long).to(device)
    logits = model(x, sym)
    probs = torch.softmax(logits, dim=-1).cpu().numpy()

    rows: list[tuple[Any, ...]] = []
    for i, symbol in enumerate(batch.symbols):
        prob_buy, prob_sell, prob_hold = probs[i].tolist()
        label_idx = int(np.argmax(probs[i]))
        confidence = float(probs[i][label_idx])
        predicted = INDEX_TO_LABEL[label_idx]

        if confidence < ML_SIGNAL_CONFIDENCE:
            logger.info(
                "Skip %s @ %s — confidence %.3f below %.2f",
                symbol,
                batch.timestamps[i],
                confidence,
                ML_SIGNAL_CONFIDENCE,
            )
            continue

        rows.append(
            (
                run_id,
                symbol,
                batch.timestamps[i].to_pydatetime(),
                predicted,
                prob_buy,
                prob_sell,
                prob_hold,
                confidence,
            )
        )

    if not rows:
        logger.warning(
            "No signals met confidence threshold %.2f", ML_SIGNAL_CONFIDENCE
        )
        return 0

    upsert = """
    INSERT INTO trading_signals (
        model_run_id, symbol, timestamp, predicted_label,
        prob_buy, prob_sell, prob_hold, confidence
    ) VALUES %s
    ON CONFLICT (model_run_id, symbol, timestamp) DO UPDATE SET
        predicted_label = EXCLUDED.predicted_label,
        prob_buy = EXCLUDED.prob_buy,
        prob_sell = EXCLUDED.prob_sell,
        prob_hold = EXCLUDED.prob_hold,
        confidence = EXCLUDED.confidence,
        created_at = NOW()
    """

    from psycopg2.extras import execute_values

    with psycopg2.connect(postgres_dsn()) as conn:
        with conn.cursor() as cur:
            execute_values(cur, upsert, rows)
        conn.commit()

    logger.info("Wrote %s trading signal(s) (confidence >= %.2f).", len(rows), ML_SIGNAL_CONFIDENCE)
    for row in rows:
        logger.info("  %s -> %s (conf=%.3f)", row[1], row[3], row[7])
    return len(rows)
