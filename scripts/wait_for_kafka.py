"""Wait until Kafka broker accepts connections."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from confluent_kafka import KafkaException
from confluent_kafka.admin import AdminClient

from src.config import KAFKA_BOOTSTRAP_SERVERS

MAX_RETRIES = 30
RETRY_DELAY_SECONDS = 2


def wait_for_kafka() -> None:
    admin = AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            metadata = admin.list_topics(timeout=5)
            broker_count = len(metadata.brokers)
            if broker_count > 0:
                print(f"Kafka is ready ({broker_count} broker(s) at {KAFKA_BOOTSTRAP_SERVERS}).")
                return
        except KafkaException as exc:
            print(f"Attempt {attempt}/{MAX_RETRIES}: Kafka not ready — {exc}")

        time.sleep(RETRY_DELAY_SECONDS)

    print("Kafka did not become ready in time.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    wait_for_kafka()
