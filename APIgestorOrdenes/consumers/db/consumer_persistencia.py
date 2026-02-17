"""
Consumer de Kafka: persiste cada orden en DynamoDB.
"""
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

from confluent_kafka import Consumer, KafkaError

from shared.config import get_settings
from shared.dynamo import get_client, ensure_table, put_orden

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_consumer():
    settings = get_settings()
    client = get_client(settings.aws_region, settings.aws_endpoint_url)
    ensure_table(client, settings.dynamo_table_ordenes)

    consumer = Consumer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": "persistencia-ordenes",
        "auto.offset.reset": "earliest",
    })
    consumer.subscribe([settings.kafka_topic_ordenes])

    logger.info("Consumer de persistencia iniciado. Topic: %s → DynamoDB %s",
                settings.kafka_topic_ordenes, settings.dynamo_table_ordenes)

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
            put_orden(client, settings.dynamo_table_ordenes, payload)
            logger.info("Orden persistida en DynamoDB: id=%s tipo=%s activo=%s",
                        payload["id"], payload["tipo"], payload["activo"])
        except Exception as e:
            logger.exception("Error persistiendo orden: %s", e)


if __name__ == "__main__":
    run_consumer()
