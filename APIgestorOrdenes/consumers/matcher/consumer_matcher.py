"""
Suscriptor matcher: solo suscrito al topic de órdenes (stub).
La lógica de matching se implementará más adelante.
"""
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from confluent_kafka import Consumer, KafkaError
from shared.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_consumer():
    settings = get_settings()
    consumer = Consumer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": "matcher-ordenes",
        "auto.offset.reset": "earliest",
    })
    consumer.subscribe([settings.kafka_topic_ordenes])

    logger.info("Consumer matcher (stub) iniciado. Suscrito a %s", settings.kafka_topic_ordenes)

    while True:
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            logger.error("Error Kafka: %s", msg.error())
            continue
        try:
            payload = json.loads(msg.value().decode("utf-8"))
            logger.info("Matcher stub - orden recibida: id=%s tipo=%s activo=%s",
                        payload.get("id"), payload.get("tipo"), payload.get("activo"))
        except Exception as e:
            logger.exception("Error en matcher stub: %s", e)


if __name__ == "__main__":
    run_consumer()
