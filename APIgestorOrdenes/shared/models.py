"""
Modelos de dominio compartidos para órdenes de compra y venta.
"""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class TipoOrden(str, Enum):
    COMPRA = "compra"
    VENTA = "venta"


class OrdenBase(BaseModel):
    tipo: TipoOrden
    activo: str = Field(..., min_length=1, description="Símbolo del activo (ej: AAPL)")
    cantidad: float = Field(..., gt=0, description="Cantidad de unidades")
    precio: float = Field(..., gt=0, description="Precio por unidad")
    cliente_id: str = Field(..., min_length=1, description="Identificador del cliente")


class OrdenCreate(OrdenBase):
    """Payload para crear una orden desde la API."""
    pass


class OrdenEvento(OrdenBase):
    """Evento publicado en Kafka (incluye id y timestamp)."""
    id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class OrdenPersistida(OrdenEvento):
    """Orden tal como se persiste en BD (puede incluir estado)."""
    estado: str = "pendiente"  # pendiente, ejecutada, cancelada


class MatchResult(BaseModel):
    """Resultado de un match entre orden de compra y venta."""
    orden_compra_id: str
    orden_venta_id: str
    cantidad_ejecutada: float
    precio: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
