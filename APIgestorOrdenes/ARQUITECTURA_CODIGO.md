# Explicación de la API a nivel de código

Este documento describe cómo está implementada la API del gestor de órdenes, capa por capa.

---

## 1. Visión general del flujo

```
Cliente  →  POST /ordenes  →  API (main.py)
                                   → Valida body con Pydantic (OrdenCreate)
                                   → orden_to_evento() → OrdenEvento (con id y timestamp)
                                   → publish_orden() → Kafka topic "ordenes"
                                   → Respuesta 200 con el evento

         →  GET /ordenes   →  API (main.py)
                                   → get_client() → DynamoDB (Localstack/AWS)
                                   → ensure_table() → crea tabla si no existe
                                   → list_ordenes() → Scan en DynamoDB
                                   → Respuesta 200 con { total, ordenes }

Kafka topic "ordenes"  →  Consumer persistencia (consumer_persistencia.py)
                                   → put_orden() → DynamoDB (tabla "ordenes")
```

---

## 2. Punto de entrada: `api/main.py`

### Carga de configuración y arranque

```python
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
```
- Carga las variables del archivo `.env` desde la **raíz del proyecto**.
- Así, aunque ejecutes `uvicorn` desde otra carpeta, se lee la misma configuración (Kafka, DynamoDB, etc.).

```python
settings = get_settings()
```
- `get_settings()` (en `shared/config.py`) devuelve un objeto `Settings` con los valores de `.env` o los valores por defecto.
- Usa **Pydantic Settings**: cada atributo de `Settings` se rellena con la variable de entorno del mismo nombre en mayúsculas (ej. `kafka_bootstrap_servers` ← `KAFKA_BOOTSTRAP_SERVERS`).

### Ciclo de vida (lifespan)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    global producer
    producer = get_producer(settings.kafka_bootstrap_servers)
    yield
    if producer:
        producer.flush(timeout=5)
```
- **Al arrancar la API:** se crea un **producer de Kafka** y se guarda en la variable global `producer`.
- **Al cerrar la API:** se hace `flush()` para enviar cualquier mensaje pendiente antes de terminar.

### Endpoints

| Ruta | Función | Qué hace |
|------|--------|----------|
| `GET /health` | `health()` | Devuelve `{"status": "ok"}`. Sirve para comprobar que la API está viva. |
| `GET /ordenes` | `listar_ordenes(limit=100)` | Lee órdenes desde DynamoDB y las devuelve (crea la tabla si no existe). |
| `POST /ordenes` | `crear_orden(orden: OrdenCreate)` | Valida el body, genera un evento y lo publica en Kafka; responde con ese evento. |

---

## 3. Modelos de datos: `shared/models.py`

Todo el flujo usa los mismos conceptos de “orden” para no duplicar reglas.

- **`TipoOrden`**: enum `"compra"` | `"venta"`.
- **`OrdenBase`**: campos comunes (`tipo`, `activo`, `cantidad`, `precio`, `cliente_id`) con validación Pydantic (`min_length`, `gt=0`, etc.).
- **`OrdenCreate`**: lo que envía el cliente en el POST (hereda de `OrdenBase`). No tiene `id` ni `timestamp`.
- **`OrdenEvento`**: lo que se publica en Kafka y se devuelve en la respuesta: `OrdenBase` + `id` (UUID) + `timestamp` (datetime).

Así, el contrato de la API (body del POST y respuesta) y el mensaje de Kafka comparten el mismo modelo de dominio.

---

## 4. Configuración: `shared/config.py`

- **`Settings`**: clase que define todas las variables de configuración (Kafka, DynamoDB, AWS).
- **`get_settings()`**: devuelve la misma instancia de `Settings` (gracias a `@lru_cache`), leyendo una sola vez el `.env`.
- **`extra = "ignore"`**: evita que Pydantic falle si en `.env` hay variables que no están definidas en `Settings` (por ejemplo `AWS_ACCESS_KEY_ID`).

---

## 5. POST /ordenes: de la petición a Kafka

### En `main.py`: `crear_orden(orden: OrdenCreate)`

1. **Validación del body**
   - FastAPI usa el tipo `OrdenCreate` para validar el JSON del POST.
   - Si falta un campo obligatorio o un valor no cumple las reglas (ej. `cantidad <= 0`), FastAPI responde 422 antes de entrar en la función.

2. **Conversión a evento**
   - `evento = orden_to_evento(orden)` (ver `api/kafka_producer.py`).
   - Se genera un `id` único (UUID) y un `timestamp` (datetime UTC).
   - El resultado es un `OrdenEvento` listo para publicar.

3. **Publicación en Kafka**
   - `publish_orden(producer, settings.kafka_topic_ordenes, evento)`.
   - Si Kafka no está disponible o falla el envío, se captura la excepción y se responde 503.

4. **Respuesta**
   - Se devuelve el mismo `evento` (con `id` y `timestamp`). FastAPI lo serializa a JSON según `OrdenEvento` (`response_model=OrdenEvento`).

### En `api/kafka_producer.py`

- **`get_producer(bootstrap_servers)`**: crea un `Producer` de `confluent_kafka` apuntando al broker (ej. `localhost:9092`).
- **`orden_to_evento(orden)`**: construye un `OrdenEvento` con `id=str(uuid.uuid4())` y `timestamp=datetime.utcnow()`.
- **`publish_orden(producer, topic, orden)`**:
  - `orden.model_dump(mode="json")` convierte el modelo a diccionario, con los `datetime` ya en formato string ISO.
  - Ese diccionario se serializa a JSON y se envía como `value` del mensaje.
  - La **key** del mensaje es el `id` de la orden (para que mensajes de la misma orden vayan a la misma partición si se usan varias).
  - `producer.flush(timeout=10)` asegura que el mensaje se envía antes de seguir.

---

## 6. GET /ordenes: de DynamoDB a la respuesta

### En `main.py`: `listar_ordenes(limit=100)`

1. **Cliente de DynamoDB**
   - `endpoint = settings.aws_endpoint_url or os.environ.get("AWS_ENDPOINT_URL")` (por si el endpoint solo está en el entorno).
   - `client = get_client(settings.aws_region, endpoint)` (ver `consumers/db/dynamo.py`).

2. **Garantizar que la tabla existe**
   - `ensure_table(client, settings.dynamo_table_ordenes)`.
   - Si la tabla no existe (por ejemplo, el consumer de persistencia no se ha ejecutado), se crea con partition key `id` (String).

3. **Leer órdenes**
   - `items = list_ordenes(client, settings.dynamo_table_ordenes, limit=limit)`.
   - Internamente hace un **Scan** en DynamoDB y convierte cada ítem del formato low-level de DynamoDB a un diccionario normal.

4. **Respuesta**
   - `{"total": len(items), "ordenes": items}` con código 200.
   - Cualquier error (por ejemplo DynamoDB no disponible) se captura y se responde 503 con el mensaje de error.

### En `consumers/db/dynamo.py`

- **`get_client(region, endpoint_url)`**: crea un cliente `boto3` de DynamoDB. Si hay `endpoint_url` (Localstack), se usan credenciales de prueba para evitar “Unable to locate credentials”.
- **`ensure_table(client, table_name)`**: `describe_table`; si la tabla no existe (`ResourceNotFoundException`), se llama a `create_table` con `id` como clave de partición y modo “pay per request”.
- **`list_ordenes(client, table_name, limit)`**: `client.scan(TableName=..., Limit=limit)` y se convierte cada ítem con `_item_to_dict` (mapear `{"S": "x"}` → `"x"`, `{"N": "123"}` → número, etc.).

---

## 7. Consumer de persistencia: de Kafka a DynamoDB

### `consumers/db/consumer_persistencia.py`

- **Arranque:**
  - Añade la raíz del proyecto al `sys.path` para poder importar `shared` y `consumers`.
  - Carga `.env` con `load_dotenv()`.
  - Obtiene configuración con `get_settings()`.
  - Crea cliente DynamoDB y llama a `ensure_table()` para la tabla de órdenes.
  - Crea un **Consumer** de Kafka con `group.id="persistencia-ordenes"` y se suscribe al topic `ordenes`.

- **Bucle principal:**
  - `consumer.poll(timeout=1.0)` espera mensajes.
  - Si hay error de Kafka (excepto “fin de partición”), se registra y se sigue.
  - Si hay mensaje:
    - Se deserializa el JSON: `payload = json.loads(msg.value().decode("utf-8"))`.
    - Ese `payload` es el mismo que la API envió (incluye `id`, `tipo`, `activo`, `cantidad`, `precio`, `cliente_id`, `timestamp`).
    - `put_orden(client, settings.dynamo_table_ordenes, payload)` escribe en DynamoDB en formato low-level (`{"id": {"S": "..."}, "cantidad": {"N": "10"}, ...}`).
  - Así, cada orden que llega por Kafka se persiste en la tabla DynamoDB que luego consulta el GET /ordenes.

---

## 8. Resumen por componente

| Componente | Responsabilidad |
|------------|-----------------|
| **api/main.py** | Entrada HTTP, lifespan del producer, GET/POST y manejo de errores (503). |
| **api/kafka_producer.py** | Crear producer, convertir `OrdenCreate` → `OrdenEvento`, publicar en Kafka. |
| **shared/models.py** | Definir y validar el dominio (OrdenCreate, OrdenEvento, etc.). |
| **shared/config.py** | Centralizar configuración desde `.env` (Settings + get_settings). |
| **consumers/db/dynamo.py** | Cliente DynamoDB, crear tabla si no existe, put_orden, list_ordenes, conversión de ítems. |
| **consumers/db/consumer_persistencia.py** | Consumir el topic `ordenes` y escribir cada mensaje en DynamoDB. |

Con esto tienes el flujo completo de la API a nivel de código: desde el POST hasta Kafka, desde Kafka hasta DynamoDB, y desde DynamoDB hasta el GET.
