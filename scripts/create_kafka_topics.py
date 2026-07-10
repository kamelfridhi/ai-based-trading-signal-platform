"""Create Kafka topics if they do not exist."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from confluent_kafka.admin import AdminClient, NewTopic

from src.config import KAFKA_BOOTSTRAP_SERVERS, KAFKA_NEWS_TOPIC, KAFKA_SOCIAL_TOPIC, KAFKA_TOPIC

TOPICS = [KAFKA_TOPIC, KAFKA_NEWS_TOPIC, KAFKA_SOCIAL_TOPIC]
MAX_RETRIES = 30
RETRY_DELAY_SECONDS = 2


def ensure_topics() -> None:
    admin = AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            existing = admin.list_topics(timeout=10).topics
            to_create = [
                NewTopic(topic, num_partitions=1, replication_factor=1)
                for topic in TOPICS
                if topic not in existing
            ]
            if not to_create:
                print(f"Kafka topics ready: {', '.join(TOPICS)}")
                return

            futures = admin.create_topics(to_create)
            for topic, future in futures.items():
                future.result()
                print(f"Created topic: {topic}")
            return
        except Exception as exc:
            print(f"Attempt {attempt}/{MAX_RETRIES}: {exc}")
            time.sleep(RETRY_DELAY_SECONDS)

    print("Could not create Kafka topics in time.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    ensure_topics()
