import asyncio
import random

from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from controller.metrics.middleware import MetricsMiddleware, init_metrics


def create_app() -> FastAPI:
    app = FastAPI()

    init_metrics()
    app.add_middleware(MetricsMiddleware)

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "OK"})

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/")
    async def index() -> PlainTextResponse:
        random_timeout_ms = random.randint(30, 69)
        await asyncio.sleep(random_timeout_ms / 1000)
        return PlainTextResponse("welcome\n")

    return app
