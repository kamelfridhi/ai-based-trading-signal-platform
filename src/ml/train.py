"""Train BiLSTM + attention classifier with focal loss."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import psycopg2
import torch
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset

from src.config import (
    INDEX_TO_LABEL,
    ML_BATCH_SIZE,
    ML_DROPOUT,
    ML_EARLY_STOP_PATIENCE,
    ML_EPOCHS,
    ML_FOCAL_GAMMA,
    ML_HIDDEN_SIZE,
    ML_LEARNING_RATE,
    ML_MODELS_DIR,
    ML_NUM_LAYERS,
    ML_SYMBOL_EMBED_DIM,
    ML_WINDOW_SIZE,
    postgres_dsn,
)
from src.ml.dataset import DataSplit, build_train_test_split
from src.ml.evaluate import compute_metrics
from src.ml.model import FocalLoss, TemporalAttentionClassifier
from src.processing.labels import FEATURE_COLUMNS

logger = logging.getLogger(__name__)

NUM_FEATURES = len(FEATURE_COLUMNS)
NUM_CLASSES = 3


def _class_weights(y: np.ndarray) -> torch.Tensor:
    counts = np.bincount(y, minlength=NUM_CLASSES).astype(np.float32)
    counts = np.maximum(counts, 1.0)
    weights = counts.sum() / (NUM_CLASSES * counts)
    return torch.tensor(weights, dtype=torch.float32)


def _make_loader(
    x: np.ndarray,
    symbol_ids: np.ndarray,
    y: np.ndarray,
    shuffle: bool,
) -> DataLoader:
    ds = TensorDataset(
        torch.tensor(x, dtype=torch.float32),
        torch.tensor(symbol_ids, dtype=torch.long),
        torch.tensor(y, dtype=torch.long),
    )
    return DataLoader(ds, batch_size=ML_BATCH_SIZE, shuffle=shuffle)


@torch.no_grad()
def _predict(
    model: TemporalAttentionClassifier,
    x: np.ndarray,
    symbol_ids: np.ndarray,
    device: torch.device,
) -> np.ndarray:
    model.eval()
    loader = _make_loader(x, symbol_ids, np.zeros(len(x), dtype=np.int64), shuffle=False)
    preds: list[int] = []
    for batch_x, batch_sym, _ in loader:
        batch_x = batch_x.to(device)
        batch_sym = batch_sym.to(device)
        logits = model(batch_x, batch_sym)
        preds.extend(logits.argmax(dim=-1).cpu().numpy().tolist())
    return np.asarray(preds, dtype=np.int64)


def _save_checkpoint(
    path: Path,
    model: TemporalAttentionClassifier,
    scaler: StandardScaler,
    symbol_to_id: dict[str, int],
    hyperparams: dict[str, Any],
    metrics: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state": model.state_dict(),
            "scaler_mean": scaler.mean_.tolist(),
            "scaler_scale": scaler.scale_.tolist(),
            "symbol_to_id": symbol_to_id,
            "hyperparams": hyperparams,
            "metrics": metrics,
            "num_features": NUM_FEATURES,
            "num_symbols": len(symbol_to_id),
            "num_classes": NUM_CLASSES,
        },
        path,
    )


def _register_model_run(path: Path, hyperparams: dict[str, Any], metrics: dict[str, Any]) -> int:
    with psycopg2.connect(postgres_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO model_runs (model_path, hyperparams, metrics)
                VALUES (%s, %s::jsonb, %s::jsonb)
                RETURNING id
                """,
                (str(path), json.dumps(hyperparams), json.dumps(metrics)),
            )
            run_id = cur.fetchone()[0]
        conn.commit()
    return int(run_id)


def train_model() -> tuple[int, Path, dict[str, Any]]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Training on device: %s", device)

    split: DataSplit = build_train_test_split()
    assert split.train.y is not None and split.test.y is not None

    num_symbols = len(split.symbol_to_id)
    model = TemporalAttentionClassifier(
        num_features=NUM_FEATURES,
        num_symbols=num_symbols,
        symbol_embed_dim=ML_SYMBOL_EMBED_DIM,
        hidden_size=ML_HIDDEN_SIZE,
        num_layers=ML_NUM_LAYERS,
        num_classes=NUM_CLASSES,
        dropout=ML_DROPOUT,
    ).to(device)

    class_weights = _class_weights(split.train.y).to(device)
    criterion = FocalLoss(gamma=ML_FOCAL_GAMMA, weight=class_weights)
    optimizer = torch.optim.Adam(model.parameters(), lr=ML_LEARNING_RATE)

    train_loader = _make_loader(
        split.train.x, split.train.symbol_ids, split.train.y, shuffle=True
    )

    best_macro_f1 = -1.0
    best_state: dict[str, Any] | None = None
    patience_left = ML_EARLY_STOP_PATIENCE

    hyperparams = {
        "window_size": ML_WINDOW_SIZE,
        "hidden_size": ML_HIDDEN_SIZE,
        "num_layers": ML_NUM_LAYERS,
        "symbol_embed_dim": ML_SYMBOL_EMBED_DIM,
        "dropout": ML_DROPOUT,
        "batch_size": ML_BATCH_SIZE,
        "epochs": ML_EPOCHS,
        "learning_rate": ML_LEARNING_RATE,
        "focal_gamma": ML_FOCAL_GAMMA,
        "split_timestamp": split.split_timestamp.isoformat(),
        "architecture": "bilstm_attention",
    }

    for epoch in range(1, ML_EPOCHS + 1):
        model.train()
        epoch_loss = 0.0
        n_batches = 0
        for batch_x, batch_sym, batch_y in train_loader:
            batch_x = batch_x.to(device)
            batch_sym = batch_sym.to(device)
            batch_y = batch_y.to(device)

            optimizer.zero_grad()
            logits = model(batch_x, batch_sym)
            loss = criterion(logits, batch_y)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()
            n_batches += 1

        y_pred = _predict(model, split.test.x, split.test.symbol_ids, device)
        metrics = compute_metrics(split.test.y, y_pred)
        macro_f1 = metrics["macro_f1"]
        logger.info(
            "Epoch %s/%s loss=%.4f macro_f1=%.4f accuracy=%.4f",
            epoch,
            ML_EPOCHS,
            epoch_loss / max(n_batches, 1),
            macro_f1,
            metrics["accuracy"],
        )

        if macro_f1 > best_macro_f1:
            best_macro_f1 = macro_f1
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            patience_left = ML_EARLY_STOP_PATIENCE
        else:
            patience_left -= 1
            if patience_left <= 0:
                logger.info("Early stopping at epoch %s", epoch)
                break

    if best_state is not None:
        model.load_state_dict(best_state)

    y_pred = _predict(model, split.test.x, split.test.symbol_ids, device)
    metrics = compute_metrics(split.test.y, y_pred)
    metrics["best_macro_f1"] = best_macro_f1

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = Path(ML_MODELS_DIR) / f"seq_classifier_{stamp}.pt"
    _save_checkpoint(path, model, split.scaler, split.symbol_to_id, hyperparams, metrics)

    run_id = _register_model_run(path, hyperparams, metrics)
    logger.info("Saved checkpoint: %s (model_run_id=%s)", path, run_id)

    for label in (0, 1, 2):
        name = INDEX_TO_LABEL[label]
        row = metrics["classification_report"].get(name, {})
        logger.info(
            "  %s precision=%.3f recall=%.3f f1=%.3f support=%s",
            name,
            row.get("precision", 0),
            row.get("recall", 0),
            row.get("f1-score", 0),
            row.get("support", 0),
        )

    return run_id, path, metrics
