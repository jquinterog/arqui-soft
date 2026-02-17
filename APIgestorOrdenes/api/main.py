"""
API FastAPI para recibir órdenes de compra y venta.
Publica cada orden en Kafka (orders.accepted, key=symbol, BUY/SELL).
"""
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from confluent_kafka import Producer
from dotenv import load_dotenv

# Cargar .env desde la raíz del proyecto (por si uvicorn se ejecuta desde otro directorio)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from shared.models import OrdenCreate, OrdenEvento
from shared.config import get_settings
from api.kafka_producer import (
    get_producer,
    orden_to_evento,
    orden_to_accepted_event,
    publish_orden_accepted,
)
from consumers.db.dynamo import (
    get_client,
    ensure_table,
    ensure_orders_table,
    ensure_order_book_table,
    ensure_trades_by_order_table,
    list_ordenes,
    query_orders,
    get_trades_by_order,
)

settings = get_settings()
producer: Producer | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global producer
    producer = get_producer(settings.kafka_bootstrap_servers)
    yield
    if producer:
        producer.flush(timeout=5)


app = FastAPI(
    title="Gestor de Órdenes",
    description="API para recibir órdenes de compra y venta. Publica eventos en Kafka.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ordenes")
def listar_ordenes(limit: int = 100):
    """Lista las órdenes persistidas en DynamoDB (para verificar que se guardaron)."""
    try:
        # Usar endpoint de settings o de env (por si .env se cargó después)
        endpoint = settings.aws_endpoint_url or os.environ.get("AWS_ENDPOINT_URL")
        client = get_client(settings.aws_region, endpoint)
        # Crear la tabla si no existe (p. ej. si el consumer de persistencia no se ha ejecutado)
        ensure_table(client, settings.dynamo_table_ordenes)
        items = list_ordenes(client, settings.dynamo_table_ordenes, limit=limit)
        return {"total": len(items), "ordenes": items}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error leyendo DynamoDB: {e}")


@app.post("/ordenes", response_model=OrdenEvento)
def crear_orden(orden: OrdenCreate):
    """Recibe una orden de compra o venta y la publica en Kafka (orders.accepted, key=symbol, BUY/SELL)."""
    if not producer:
        raise HTTPException(status_code=503, detail="Kafka no disponible")
    evento = orden_to_evento(orden)
    ts_ms = int(time.time() * 1000)
    accepted = orden_to_accepted_event(orden, order_id=evento.id, ts_ms=ts_ms)
    try:
        publish_orden_accepted(producer, settings.kafka_topic_orders_accepted, accepted)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error publicando en Kafka: {e}")
    return evento


@app.get("/orders")
def list_orders(
    symbol: str | None = None,
    status: str | None = None,
    matched: bool | None = None,
    limit: int = 100,
):
    """Lista órdenes de la tabla orders con filtros opcionales (symbol, status, matched)."""
    try:
        endpoint = settings.aws_endpoint_url or os.environ.get("AWS_ENDPOINT_URL")
        client = get_client(settings.aws_region, endpoint)
        ensure_orders_table(client, settings.dynamo_table_orders)
        items = query_orders(
            client,
            settings.dynamo_table_orders,
            symbol=symbol,
            status=status,
            matched=matched,
            limit=limit,
        )
        return {"total": len(items), "orders": items}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/orders/{order_id}/trades")
def list_order_trades(order_id: str, limit: int = 100):
    """Lista los trades de una orden (tabla trades_by_order)."""
    try:
        endpoint = settings.aws_endpoint_url or os.environ.get("AWS_ENDPOINT_URL")
        client = get_client(settings.aws_region, endpoint)
        ensure_trades_by_order_table(client, settings.dynamo_table_trades_by_order)
        items = get_trades_by_order(
            client, settings.dynamo_table_trades_by_order, order_id, limit=limit
        )
        return {"order_id": order_id, "total": len(items), "trades": items}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
