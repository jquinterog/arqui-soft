"""
Producer de Kafka para publicar eventos de órdenes.
"""
import json
import uuid
from datetime import datetime
from confluent_kafka import Producer
from shared.models import OrdenCreate, OrdenEvento, TipoOrden


def get_producer(bootstrap_servers: str) -> Producer:
    return Producer({"bootstrap.servers": bootstrap_servers})


def orden_to_evento(orden: OrdenCreate) -> OrdenEvento:
    return OrdenEvento(
        id=str(uuid.uuid4()),
        tipo=orden.tipo,
        activo=orden.activo,
        cantidad=orden.cantidad,
        precio=orden.precio,
        cliente_id=orden.cliente_id,
        timestamp=datetime.utcnow(),
    )


def publish_orden(producer: Producer, topic: str, orden: OrdenEvento) -> None:
    # mode="json" ya serializa datetime a string ISO
    payload = orden.model_dump(mode="json")
    producer.produce(
        topic=topic,
        value=json.dumps(payload).encode("utf-8"),
        key=orden.id.encode("utf-8"),
    )
    producer.flush(timeout=10)
