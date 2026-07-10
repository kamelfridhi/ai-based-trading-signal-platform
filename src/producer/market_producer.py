"""Real market data producer — Yahoo Finance OHLCV, news, and related tweets → Kafka."""

from __future__ import annotations

import json
import logging
import signal
import sys
import time
from typing import Any

from confluent_kafka import Producer

from src.config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_NEWS_TOPIC,
    KAFKA_SOCIAL_TOPIC,
    KAFKA_TOPIC,
    NEWS_INTERVAL_SECONDS,
    NEWS_MAX_PER_SYMBOL,
    PRODUCER_INTERVAL_SECONDS,
    SYMBOLS,
    TWEET_INTERVAL_SECONDS,
    TWEETS_MAX_PER_SYMBOL,
    TWITTER_BEARER_TOKEN,
)
from src.sources.twitter import fetch_tweets
from src.sources.yahoo import fetch_news, fetch_ohlcv_batch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

running = True
seen_news_ids: set[str] = set()
seen_tweet_ids: set[str] = set()


def _shutdown_handler(signum: int, frame: Any) -> None:
    global running
    logger.info("Shutdown signal received (%s). Finishing up...", signum)
    running = False


def _delivery_callback(err: Any, msg: Any) -> None:
    if err:
        logger.error("Message delivery failed: %s", err)
    else:
        logger.debug(
            "Delivered to %s [%s] @ offset %s",
            msg.topic(),
            msg.partition(),
            msg.offset(),
        )


def _publish(producer: Producer, topic: str, key: str, event: dict[str, Any]) -> None:
    payload = json.dumps(event)
    producer.produce(
        topic,
        key=key.encode("utf-8"),
        value=payload.encode("utf-8"),
        callback=_delivery_callback,
    )
    producer.poll(0)
    logger.info("Published to %s: %s", topic, payload)


def _publish_market_data(producer: Producer) -> None:
    for event in fetch_ohlcv_batch(SYMBOLS):
        if not running:
            return
        _publish(producer, KAFKA_TOPIC, event["symbol"], event)


def _publish_news(producer: Producer) -> None:
    for symbol in SYMBOLS:
        if not running:
            return
        for event in fetch_news(symbol, max_items=NEWS_MAX_PER_SYMBOL):
            news_id = event["news_id"]
            if news_id in seen_news_ids:
                continue
            seen_news_ids.add(news_id)
            _publish(producer, KAFKA_NEWS_TOPIC, symbol, event)
        time.sleep(5.0)


def _publish_tweets(producer: Producer) -> None:
    if not TWITTER_BEARER_TOKEN:
        return

    for symbol in SYMBOLS:
        if not running:
            return
        for event in fetch_tweets(symbol, max_results=TWEETS_MAX_PER_SYMBOL):
            tweet_id = event["tweet_id"]
            if tweet_id in seen_tweet_ids:
                continue
            seen_tweet_ids.add(tweet_id)
            _publish(producer, KAFKA_SOCIAL_TOPIC, symbol, event)
        time.sleep(1.0)


def main() -> None:
    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)

    producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})
    last_news_fetch = 0.0
    last_tweet_fetch = 0.0

    logger.info(
        "Starting real-data producer | symbols=%s market=%s news=%s social=%s",
        ",".join(SYMBOLS),
        KAFKA_TOPIC,
        KAFKA_NEWS_TOPIC,
        KAFKA_SOCIAL_TOPIC,
    )

    if not TWITTER_BEARER_TOKEN:
        logger.info("Tweet ingestion disabled (TWITTER_BEARER_TOKEN not set).")

    while running:
        now = time.monotonic()

        _publish_market_data(producer)

        if now - last_news_fetch >= NEWS_INTERVAL_SECONDS:
            _publish_news(producer)
            last_news_fetch = now

        if now - last_tweet_fetch >= TWEET_INTERVAL_SECONDS:
            _publish_tweets(producer)
            last_tweet_fetch = now

        time.sleep(PRODUCER_INTERVAL_SECONDS)

    producer.flush(timeout=10)
    logger.info("Producer stopped cleanly.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted.")
        sys.exit(0)
