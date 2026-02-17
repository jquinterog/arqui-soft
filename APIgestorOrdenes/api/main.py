"""
API FastAPI para recibir órdenes de compra y venta.
Publica cada orden como evento en Kafka.
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from confluent_kafka import Producer
from dotenv import load_dotenv

# Cargar .env desde la raíz del proyecto (por si uvicorn se ejecuta desde otro directorio)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from shared.models import OrdenCreate, OrdenEvento
from shared.config import get_settings
from api.kafka_producer import get_producer, orden_to_evento, publish_orden
from shared.dynamo import get_client, ensure_table, list_ordenes

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
    """Recibe una orden de compra o venta y la publica en Kafka."""
    if not producer:
        raise HTTPException(status_code=503, detail="Kafka no disponible")
    evento = orden_to_evento(orden)
    try:
        publish_orden(producer, settings.kafka_topic_ordenes, evento)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error publicando en Kafka: {e}")
    return evento
