"""FinBERT sentiment scoring for market news."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import psycopg2
import torch
from psycopg2.extensions import connection as PgConnection
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from src.config import FINBERT_MODEL, SENTIMENT_BATCH_SIZE, postgres_dsn

logger = logging.getLogger(__name__)

_tokenizer: AutoTokenizer | None = None
_model: AutoModelForSequenceClassification | None = None


@dataclass
class SentimentResult:
    news_id: int
    label: str
    score: float
    value: float


def _get_model() -> tuple[AutoTokenizer, AutoModelForSequenceClassification]:
    global _tokenizer, _model
    if _tokenizer is None or _model is None:
        logger.info("Loading FinBERT model: %s (first run downloads ~400MB)...", FINBERT_MODEL)
        _tokenizer = AutoTokenizer.from_pretrained(FINBERT_MODEL)
        _model = AutoModelForSequenceClassification.from_pretrained(FINBERT_MODEL)
        _model.eval()
    return _tokenizer, _model


def _label_map(model: AutoModelForSequenceClassification) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for key, label in model.config.id2label.items():
        mapping[int(key)] = label.lower()
    return mapping


def score_texts(texts: list[str]) -> list[tuple[str, float, float]]:
    """Score a batch of texts. Returns (label, confidence, sentiment_value)."""
    if not texts:
        return []

    tokenizer, model = _get_model()
    id2label = _label_map(model)

    positive_idx = next(idx for idx, label in id2label.items() if label == "positive")
    negative_idx = next(idx for idx, label in id2label.items() if label == "negative")

    results: list[tuple[str, float, float]] = []
    for start in range(0, len(texts), SENTIMENT_BATCH_SIZE):
        batch = texts[start : start + SENTIMENT_BATCH_SIZE]
        inputs = tokenizer(
            batch,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        with torch.no_grad():
            logits = model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)

        for row in probs:
            confidence, label_idx = torch.max(row, dim=0)
            label = id2label[int(label_idx)]
            confidence_f = float(confidence)
            sentiment_value = float(row[positive_idx] - row[negative_idx])
            results.append((label, confidence_f, sentiment_value))

    return results


def _load_unscored_news(conn: PgConnection) -> list[tuple[int, str]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, title
            FROM market_news
            WHERE sentiment_label IS NULL
            ORDER BY published_at ASC
            """
        )
        return [(row[0], row[1]) for row in cur.fetchall()]


def _save_sentiments(conn: PgConnection, results: list[SentimentResult]) -> None:
    with conn.cursor() as cur:
        for item in results:
            cur.execute(
                """
                UPDATE market_news
                SET sentiment_label = %s,
                    sentiment_score = %s,
                    sentiment_value = %s
                WHERE id = %s
                """,
                (item.label, item.score, item.value, item.news_id),
            )
    conn.commit()


def process_all_news() -> int:
    """Score all unscored news articles. Returns number of rows updated."""
    with psycopg2.connect(postgres_dsn()) as conn:
        pending = _load_unscored_news(conn)
        if not pending:
            logger.info("No unscored news articles found.")
            return 0

        logger.info("Scoring %s news articles with FinBERT...", len(pending))
        news_ids = [item[0] for item in pending]
        titles = [item[1] or "" for item in pending]
        scored = score_texts(titles)

        results = [
            SentimentResult(
                news_id=news_id,
                label=label,
                score=score,
                value=value,
            )
            for news_id, (label, score, value) in zip(news_ids, scored, strict=True)
        ]
        _save_sentiments(conn, results)
        logger.info("Scored %s news articles.", len(results))
        return len(results)
