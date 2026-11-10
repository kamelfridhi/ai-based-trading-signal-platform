"""Classification metrics for walk-forward test split."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)

from src.config import INDEX_TO_LABEL


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    labels = [INDEX_TO_LABEL[i] for i in range(3)]
    report = classification_report(
        y_true,
        y_pred,
        labels=[0, 1, 2],
        target_names=labels,
        output_dict=True,
        zero_division=0,
    )
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1, 2])
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "classification_report": report,
        "confusion_matrix": cm.tolist(),
        "support": {
            "BUY": int((y_true == 0).sum()),
            "SELL": int((y_true == 1).sum()),
            "HOLD": int((y_true == 2).sum()),
        },
    }
