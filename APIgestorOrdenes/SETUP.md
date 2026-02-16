# Cómo levantar el proyecto

## Qué necesitas tener instalado

| Requisito | Para qué | Dónde conseguirlo |
|-----------|----------|--------------------|
| **Python 3.11 o superior** | API y consumers | [python.org](https://www.python.org/downloads/) |
| **Docker Desktop** | Kafka y (opcional) DynamoDB local con Localstack | [docker.com](https://www.docker.com/products/docker-desktop/) |
| **Git** (opcional) | Solo si clonas el repo | [git-scm.com](https://git-scm.com/) |

### Comprobar instalaciones

En PowerShell o CMD:

```powershell
python --version    # debe ser 3.11 o mayor
docker --version
docker compose version
```

---

## Opción A: Todo local (Kafka + DynamoDB con Localstack)

Así no necesitas cuenta de AWS. DynamoDB corre en Docker (Localstack).

### 1. Clonar/abrir el proyecto y entrar en la carpeta

```powershell
cd "c:\Users\willi\Documents\Universidad\Arqutiectura de Software\Desarrollo\gestorOrdenes"
```

### 2. Crear entorno virtual e instalar dependencias

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Si en PowerShell da error de ejecución de scripts:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Luego vuelve a ejecutar `.\venv\Scripts\Activate.ps1`.

### 3. Levantar Kafka y Localstack (DynamoDB local) con Docker

```powershell
docker compose up -d
```

Espera unos 20–30 segundos a que Kafka y Localstack estén listos.

**Si sale "image not found"**: el proyecto usa la imagen oficial **apache/kafka** (no Bitnami). Si tampoco se descarga, comprueba conexión a Internet, prueba `docker pull apache/kafka:latest` o inicia sesión en Docker Hub con `docker login`.

### 4. Variables de entorno

Copia el ejemplo y déjalo listo para Localstack:

```powershell
copy .env.example .env
```

El `.env.example` ya trae lo necesario para Localstack. Si falta, asegúrate de tener:

```env
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_ORDENES=ordenes
DYNAMO_TABLE_ORDENES=ordenes
AWS_REGION=us-east-1
AWS_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
```

### 5. Levantar la API

En una terminal, con el `venv` activado y desde la raíz del proyecto:

```powershell
$env:PYTHONPATH = (Get-Location).Path
uvicorn api.main:app --reload --port 8000
```

Deberías ver algo como: `Uvicorn running on http://127.0.0.1:8000`.

### 6. Levantar los dos consumers (otras dos terminales)

En cada una: activar el venv, ir a la raíz del proyecto y poner `PYTHONPATH`:

**Terminal 2 – Consumer persistencia (DynamoDB):**

```powershell
cd "c:\Users\willi\Documents\Universidad\Arqutiectura de Software\Desarrollo\gestorOrdenes"
.\venv\Scripts\Activate.ps1
$env:PYTHONPATH = (Get-Location).Path
python -m consumers.db.consumer_persistencia
```

**Terminal 3 – Consumer matcher (stub):**

```powershell
cd "c:\Users\willi\Documents\Universidad\Arqutiectura de Software\Desarrollo\gestorOrdenes"
.\venv\Scripts\Activate.ps1
$env:PYTHONPATH = (Get-Location).Path
python -m consumers.matcher.consumer_matcher
```

### 7. Probar

- Documentación de la API: http://localhost:8000/docs  
- Health: http://localhost:8000/health  

Crear una orden (en otra terminal o desde el navegador/docs):

```powershell
curl -X POST http://localhost:8000/ordenes -H "Content-Type: application/json" -d "{\"tipo\": \"compra\", \"activo\": \"AAPL\", \"cantidad\": 10, \"precio\": 150.5, \"cliente_id\": \"cli-001\"}"
```

En las terminales de los consumers deberías ver los logs de la orden recibida y guardada en DynamoDB (Localstack).

---

## Opción B: Kafka local + DynamoDB en AWS real

Si quieres usar DynamoDB en la nube:

1. Instala **AWS CLI** y configura credenciales: `aws configure`.
2. No levantes Localstack: en `docker-compose` comenta o quita el servicio `localstack`, o usa un `docker-compose` que solo tenga Kafka.
3. En `.env` **no** pongas `AWS_ENDPOINT_URL` (o déjalo vacío). Pon tu `AWS_REGION` y deja que use tu perfil/credenciales de AWS.
4. Sigue los mismos pasos 1, 2, 5, 6 y 7 de la Opción A; el consumer de persistencia creará la tabla en DynamoDB si tiene permisos.

---

## Resumen rápido (Opción A – todo local)

```powershell
cd "c:\Users\willi\Documents\Universidad\Arqutiectura de Software\Desarrollo\gestorOrdenes"
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Editar .env y poner AWS_ENDPOINT_URL=http://localhost:4566
docker compose up -d
# Esperar ~30 s, luego en 3 terminales (con venv activado y PYTHONPATH):
# Terminal 1: uvicorn api.main:app --reload --port 8000
# Terminal 2: python -m consumers.db.consumer_persistencia
# Terminal 3: python -m consumers.matcher.consumer_matcher
```

---

## Parar todo

- API y consumers: `Ctrl+C` en cada terminal.
- Kafka y Localstack: `docker compose down`.
