"""
Acceso a DynamoDB para persistir y consultar órdenes.
"""
import os
from datetime import datetime

import boto3


def get_client(region: str, endpoint_url: str | None = None):
    # Resolver endpoint (por si viene en env y no en settings)
    url = endpoint_url or os.environ.get("AWS_ENDPOINT_URL") or None
    if isinstance(url, str):
        url = url.strip() or None
    kwargs = {"region_name": region}
    if url:
        kwargs["endpoint_url"] = url
        # Localstack acepta cualquier credencial; así evitamos "Unable to locate credentials"
        kwargs["aws_access_key_id"] = os.environ.get("AWS_ACCESS_KEY_ID", "test")
        kwargs["aws_secret_access_key"] = os.environ.get("AWS_SECRET_ACCESS_KEY", "test")
    return boto3.client("dynamodb", **kwargs)


def ensure_table(client, table_name: str):
    """Crea la tabla si no existe (id como partition key)."""
    try:
        client.describe_table(TableName=table_name)
        return
    except client.exceptions.ResourceNotFoundException:
        pass
    client.create_table(
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "id", "KeyType": "HASH"},
        ],
    )
    # Esperar a que la tabla esté activa
    waiter = client.get_waiter("table_exists")
    waiter.wait(TableName=table_name)


def put_orden(client, table_name: str, payload: dict):
    """Guarda una orden en DynamoDB."""
    timestamp = payload.get("timestamp")
    if isinstance(timestamp, str):
        created_at = timestamp
    else:
        created_at = datetime.utcnow().isoformat() + "Z"
    client.put_item(
        TableName=table_name,
        Item={
            "id": {"S": payload["id"]},
            "tipo": {"S": payload["tipo"]},
            "activo": {"S": payload["activo"]},
            "cantidad": {"N": str(float(payload["cantidad"]))},
            "precio": {"N": str(float(payload["precio"]))},
            "cliente_id": {"S": payload["cliente_id"]},
            "estado": {"S": "pendiente"},
            "created_at": {"S": created_at},
        },
    )


def _item_to_dict(item: dict) -> dict:
    """Convierte un Item de DynamoDB (formato low-level) a dict normal."""
    result = {}
    for k, v in item.items():
        if "S" in v:
            result[k] = v["S"]
        elif "N" in v:
            result[k] = float(v["N"]) if "." in v["N"] or "e" in v["N"].lower() else int(v["N"])
        elif "BOOL" in v:
            result[k] = v["BOOL"]
        else:
            result[k] = v
    return result


def list_ordenes(client, table_name: str, limit: int = 100) -> list[dict]:
    """Lista órdenes guardadas en DynamoDB (scan)."""
    response = client.scan(TableName=table_name, Limit=limit)
    return [_item_to_dict(item) for item in response.get("Items", [])]
