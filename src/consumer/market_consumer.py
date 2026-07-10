"""Kafka consumer — reads market, news, and social events into PostgreSQL."""

from __future__ import annotations

import json
import logging
import signal
import sys
import time
from datetime import datetime
from typing import Any

import psycopg2
from confluent_kafka import Consumer, KafkaError, KafkaException
from confluent_kafka.admin import AdminClient, NewTopic
from psycopg2.extensions import connection as PgConnection

from src.config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_NEWS_TOPIC,
    KAFKA_SOCIAL_TOPIC,
    KAFKA_TOPIC,
    postgres_dsn,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

OHLCV_FIELDS = ("symbol", "timestamp", "open", "high", "low", "close", "volume")
NEWS_FIELDS = ("news_id", "symbol", "title", "published_at")
TWEET_FIELDS = ("tweet_id", "symbol", "text")

running = True


def _shutdown_handler(signum: int, frame: Any) -> None:
    global running
    logger.info("Shutdown signal received (%s). Finishing up...", signum)
    running = False


def _connect_db(max_retries: int = 30, delay: float = 2.0) -> PgConnection:
    """Connect to PostgreSQL with simple retry logic."""
    for attempt in range(1, max_retries + 1):
        try:
            conn = psycopg2.connect(postgres_dsn())
            conn.autocommit = False
            logger.info("Connected to PostgreSQL.")
            return conn
        except psycopg2.OperationalError as exc:
            logger.warning(
                "PostgreSQL not ready (attempt %s/%s): %s",
                attempt,
                max_retries,
                exc,
            )
            time.sleep(delay)
    raise RuntimeError("Could not connect to PostgreSQL after retries.")


def _validate_fields(data: dict[str, Any], required: tuple[str, ...]) -> None:
    missing = [field for field in required if field not in data]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _insert_ohlcv(conn: PgConnection, data: dict[str, Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO market_events
                (symbol, timestamp, open, high, low, close, volume)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                data["symbol"],
                _parse_timestamp(data["timestamp"]),
                data["open"],
                data["high"],
                data["low"],
                data["close"],
                data["volume"],
            ),
        )
    conn.commit()


def _insert_news(conn: PgConnection, data: dict[str, Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO market_news
                (news_id, symbol, title, publisher, link, summary, published_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (news_id) DO NOTHING
            """,
            (
                data["news_id"],
                data["symbol"],
                data["title"],
                data.get("publisher", ""),
                data.get("link", ""),
                data.get("summary", ""),
                _parse_timestamp(data["published_at"]),
            ),
        )
    conn.commit()


def _insert_tweet(conn: PgConnection, data: dict[str, Any]) -> None:
    created_at = None
    if data.get("created_at"):
        created_at = _parse_timestamp(data["created_at"])

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO market_tweets
                (tweet_id, symbol, author, text, created_at, retweet_count, like_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (tweet_id) DO NOTHING
            """,
            (
                data["tweet_id"],
                data["symbol"],
                data.get("author", ""),
                data["text"],
                created_at,
                data.get("retweet_count", 0),
                data.get("like_count", 0),
            ),
        )
    conn.commit()


def _process_message(conn: PgConnection, topic: str, data: dict[str, Any]) -> None:
    if topic == KAFKA_TOPIC:
        _validate_fields(data, OHLCV_FIELDS)
        _insert_ohlcv(conn, data)
        logger.info("Stored OHLCV %s @ %s", data["symbol"], data["timestamp"])
        return

    if topic == KAFKA_NEWS_TOPIC:
        _validate_fields(data, NEWS_FIELDS)
        _insert_news(conn, data)
        logger.info("Stored news %s for %s", data["news_id"], data["symbol"])
        return

    if topic == KAFKA_SOCIAL_TOPIC:
        _validate_fields(data, TWEET_FIELDS)
        _insert_tweet(conn, data)
        logger.info("Stored tweet %s for %s", data["tweet_id"], data["symbol"])
        return

    raise ValueError(f"Unknown topic: {topic}")


def _ensure_kafka_topics() -> None:
    """Create Kafka topics before subscribing (avoids UNKNOWN_TOPIC_OR_PART errors)."""
    admin = AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})
    topics = [KAFKA_TOPIC, KAFKA_NEWS_TOPIC, KAFKA_SOCIAL_TOPIC]

    for attempt in range(1, 31):
        try:
            existing = admin.list_topics(timeout=10).topics
            to_create = [
                NewTopic(topic, num_partitions=1, replication_factor=1)
                for topic in topics
                if topic not in existing
            ]
            if to_create:
                futures = admin.create_topics(to_create)
                for topic, future in futures.items():
                    future.result()
                    logger.info("Created Kafka topic: %s", topic)
            return
        except Exception as exc:
            logger.warning(
                "Kafka topics not ready (attempt %s/30): %s",
                attempt,
                exc,
            )
            time.sleep(2)

    raise RuntimeError("Could not ensure Kafka topics exist.")


def main() -> None:
    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)

    _ensure_kafka_topics()

    consumer = Consumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "group.id": "market-consumer-group",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    topics = [KAFKA_TOPIC, KAFKA_NEWS_TOPIC, KAFKA_SOCIAL_TOPIC]
    consumer.subscribe(topics)

    conn = _connect_db()

    logger.info(
        "Starting market consumer | topics=%s bootstrap=%s",
        topics,
        KAFKA_BOOTSTRAP_SERVERS,
    )

    try:
        while running:
            msg = consumer.poll(1.0)
            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise KafkaException(msg.error())

            try:
                data = json.loads(msg.value().decode("utf-8"))
                _process_message(conn, msg.topic(), data)
                consumer.commit(message=msg, asynchronous=False)
            except (json.JSONDecodeError, ValueError, psycopg2.Error) as exc:
                logger.error("Failed to process message on %s: %s", msg.topic(), exc)
                conn.rollback()
    finally:
        consumer.close()
        conn.close()
        logger.info("Consumer stopped cleanly.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted.")
        sys.exit(0)
