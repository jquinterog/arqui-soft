# Gestor de Órdenes (Compra/Venta)

API en Python que recibe órdenes de compra y venta, las publica en **Kafka** (topic `ordenes`) y un **suscriptor** persiste cada orden en **DynamoDB**. Un segundo suscriptor queda como **stub** (solo suscrito al topic, sin lógica de matching).

## Arquitectura

```
  Cliente → API (FastAPI) → Kafka (topic: orders.accepted, key=symbol)
                                  └→ Engine worker → DynamoDB (orders, order_book, trades_by_order) + matching
```

## Estructura

```
gestorOrdenes/
├── api/                    # API FastAPI + producer Kafka
│   ├── main.py
│   └── kafka_producer.py
├── consumers/
│   ├── db/                  # Persistencia en DynamoDB
│   │   ├── engine_worker.py
│   │   └── dynamo.py
│   └── matcher/             # Stub (solo suscripción)
│       └── consumer_matcher.py
├── shared/
│   ├── models.py
│   └── config.py
├── k8s/                     # Kubernetes (Kafka + API + 2 consumers)
├── Dockerfile.api
├── Dockerfile.consumer-db
├── Dockerfile.consumer-matcher
└── requirements.txt
```

## Requisitos

- Python 3.11+
- Docker (para Kafka y, opcionalmente, Localstack como DynamoDB local)
- Cuenta AWS con DynamoDB **o** Localstack para desarrollo local (sin AWS)

**Guía paso a paso para levantar el proyecto:** ver **[SETUP.md](SETUP.md)**.

## Desarrollo local

1. Entorno e dependencias:

   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Levantar solo Kafka:

   ```bash
   docker compose up -d
   ```

3. Variables de entorno (`.env` o export):

   - `KAFKA_BOOTSTRAP_SERVERS=localhost:9092`
   - `KAFKA_TOPIC_ORDENES=ordenes`
   - `DYNAMO_TABLE_ORDENES=ordenes`
   - `AWS_REGION=us-east-1`
   - Credenciales AWS (perfil o `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`)
   - Opcional: `AWS_ENDPOINT_URL=http://localhost:4566` para Localstack

4. Ejecutar API (desde la raíz):

   ```bash
   set PYTHONPATH=%CD%
   uvicorn api.main:app --reload --port 8000
   ```

5. En otras terminales, consumers:

   ```bash
   python -m consumers.db.engine_worker
   python -m consumers.matcher.consumer_matcher
   ```

## Despliegue en Kubernetes

- Se despliega **Kafka**, la **API** y los **consumers** (engine_worker + matcher stub).
- **DynamoDB** no se despliega en el cluster: el engine_worker usa la API de AWS (necesita credenciales o IAM Role for Service Account).

1. Crear la tabla en DynamoDB (una vez, en AWS):

   - Nombre: `ordenes` (o el que uses en `DYNAMO_TABLE_ORDENES`)
   - Partition key: `id` (String)
   - O dejar que el consumer la cree al arrancar (si tiene permisos `dynamodb:CreateTable`).

2. Construir imágenes:

   ```bash
   docker build -f Dockerfile.api -t gestor-ordenes-api:latest .
   docker build -f Dockerfile.consumer-db -t gestor-ordenes-consumer-db:latest .
   docker build -f Dockerfile.consumer-matcher -t gestor-ordenes-consumer-matcher:latest .
   ```

3. Cargar en el cluster (ej. minikube):

   ```bash
   minikube image load gestor-ordenes-api:latest
   minikube image load gestor-ordenes-consumer-db:latest
   minikube image load gestor-ordenes-consumer-matcher:latest
   ```

4. Credenciales AWS para el engine_worker: Secret con `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY`, o usar IRSA (IAM Role for Service Account) en EKS.

5. Aplicar manifiestos:

   ```bash
   kubectl apply -k k8s/
   ```

## API

- **GET /health** – Estado del servicio.
- **POST /ordenes** – Crea una orden y la publica en Kafka. Body JSON:
  - `tipo`: `"compra"` o `"venta"`
  - `activo`: símbolo (ej. `"AAPL"`)
  - `cantidad`: número > 0
  - `precio`: número > 0
  - `cliente_id`: identificador del cliente

Respuesta: orden con `id` y `timestamp`. El engine_worker consume `orders.accepted`, persiste en DynamoDB (orders, order_book, trades_by_order) y ejecuta matching. Ver también **GET /orders** (filtros: symbol, status, matched) y **GET /orders/{order_id}/trades**.
