"""
Borra las tablas de DynamoDB del proyecto (orders, order_book, trades_by_order, ordenes).
Al volver a levantar el engine_worker, las tablas se recrean vacías.

Uso (desde la raíz del proyecto, con venv activado):
  set PYTHONPATH=%CD%
  python scripts/clear_dynamo.py

En PowerShell:
  $env:PYTHONPATH = (Get-Location).Path
  python scripts/clear_dynamo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv()

from shared.config import get_settings
from consumers.db.dynamo import get_client


def main():
    settings = get_settings()
    client = get_client(settings.aws_region, settings.aws_endpoint_url)
    tables = [
        settings.dynamo_table_orders,
        settings.dynamo_table_order_book,
        settings.dynamo_table_trades_by_order,
        settings.dynamo_table_ordenes,
    ]
    for name in tables:
        try:
            client.delete_table(TableName=name)
            print(f"Tabla borrada: {name}")
        except client.exceptions.ResourceNotFoundException:
            print(f"Tabla no existía: {name}")
        except Exception as e:
            print(f"Error borrando {name}: {e}")
    print("Listo. Vuelve a levantar el engine_worker para recrear orders/order_book/trades_by_order.")


if __name__ == "__main__":
    main()
