"""
Engine worker: consume topic orders.accepted, persiste en orders/order_book,
ejecuta matching y registra trades. Usa TransactWriteItems para atomicidad.

POC: ejecutar con una sola réplica (replicas=1).
Para escalar: usar lock por symbol (ej. DynamoDB conditional write por symbol#lock
o Redis/DLM) para que solo un worker procese órdenes de un mismo symbol a la vez.
"""
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

from confluent_kafka import Consumer, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic

from shared.config import get_settings
from consumers.db.dynamo import (
    get_client,
    ensure_orders_table,
    ensure_order_book_table,
    ensure_trades_by_order_table,
    run_order_accepted,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _ensure_topic(bootstrap_servers: str, topic: str):
    """Crea el topic en Kafka si no existe (evita UNKNOWN_TOPIC_OR_PART al suscribirse)."""
    admin = AdminClient({"bootstrap.servers": bootstrap_servers})
    try:
        metadata = admin.list_topics(timeout=10)
        if metadata.topics.get(topic) is not None:
            return
    except Exception as e:
        logger.warning("No se pudo listar topics (Kafka puede estar arrancando): %s", e)
    fs = admin.create_topics([NewTopic(topic, num_partitions=1, replication_factor=1)])
    for t, f in fs.items():
        try:
            f.result(timeout=10)
            logger.info("Topic creado: %s", t)
        except Exception as e:
            if "already exists" in str(e).lower() or "TopicExistsException" in str(type(e).__name__):
                pass
            else:
                logger.warning("Crear topic %s: %s", t, e)


def run_consumer():
    settings = get_settings()
    _ensure_topic(settings.kafka_bootstrap_servers, settings.kafka_topic_orders_accepted)

    client = get_client(settings.aws_region, settings.aws_endpoint_url)
    ensure_orders_table(client, settings.dynamo_table_orders)
    ensure_order_book_table(client, settings.dynamo_table_order_book)
    ensure_trades_by_order_table(client, settings.dynamo_table_trades_by_order)

    consumer = Consumer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": "engine-worker-orders",
        "auto.offset.reset": "earliest",
    })
    consumer.subscribe([settings.kafka_topic_orders_accepted])

    logger.info(
        "Engine worker iniciado. Topic: %s → orders / order_book / trades_by_order",
        settings.kafka_topic_orders_accepted,
    )

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
            order_id = payload["order_id"]
            symbol = payload["symbol"]
            side = payload["side"]
            price_cents = int(payload["price_cents"])
            qty = float(payload["qty"])
            cliente_id = payload["cliente_id"]
            ts_ms = int(payload["ts_ms"])

            run_order_accepted(
                client,
                settings.dynamo_table_orders,
                settings.dynamo_table_order_book,
                settings.dynamo_table_trades_by_order,
                order_id=order_id,
                symbol=symbol,
                side=side,
                price_cents=price_cents,
                qty=qty,
                cliente_id=cliente_id,
                ts_ms=ts_ms,
            )
            logger.info(
                "Orden procesada: order_id=%s symbol=%s side=%s → orders + order_book + matching",
                order_id, symbol, side,
            )
        except Exception as e:
            logger.exception("Error procesando orden: %s", e)


if __name__ == "__main__":
    run_consumer()
