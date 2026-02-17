"""
Producer de Kafka para publicar eventos de órdenes.
POST /ordenes publica en topic orders.accepted con key=symbol y payload BUY/SELL.
"""
import json
import time
import uuid
from datetime import datetime
from confluent_kafka import Producer
from shared.models import OrdenCreate, OrdenEvento, OrderAcceptedEvent, OrderSide, TipoOrden


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


def orden_to_accepted_event(orden: OrdenCreate, order_id: str, ts_ms: int) -> OrderAcceptedEvent:
    """Convierte OrdenCreate a evento orders.accepted (BUY/SELL, price_cents)."""
    side = OrderSide.BUY if orden.tipo == TipoOrden.COMPRA else OrderSide.SELL
    price_cents = int(round(orden.precio * 100))
    return OrderAcceptedEvent(
        order_id=order_id,
        symbol=orden.activo,
        side=side,
        price_cents=price_cents,
        qty=orden.cantidad,
        cliente_id=orden.cliente_id,
        ts_ms=ts_ms,
    )


def publish_orden_accepted(producer: Producer, topic: str, event: OrderAcceptedEvent) -> None:
    """Publica en orders.accepted con key=symbol (para particionado por símbolo)."""
    payload = event.model_dump(mode="json")
    producer.produce(
        topic=topic,
        value=json.dumps(payload).encode("utf-8"),
        key=event.symbol.encode("utf-8"),
    )
    producer.flush(timeout=10)


def publish_orden(producer: Producer, topic: str, orden: OrdenEvento) -> None:
    """Legacy: publica OrdenEvento (compra/venta) en topic dado con key=id."""
    payload = orden.model_dump(mode="json")
    producer.produce(
        topic=topic,
        value=json.dumps(payload).encode("utf-8"),
        key=orden.id.encode("utf-8"),
    )
    producer.flush(timeout=10)
