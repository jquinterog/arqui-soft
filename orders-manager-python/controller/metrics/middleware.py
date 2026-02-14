import logging
import time

from fastapi import Request
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(
        0.001,
        0.0025,
        0.005,
        0.0075,
        0.01,
        0.015,
        0.02,
        0.025,
        0.03,
        0.04,
        0.05,
        0.06,
        0.07,
        0.08,
        0.09,
        0.10,
        0.125,
        0.15,
        0.175,
        0.2,
        0.25,
        0.3,
        0.4,
        0.5,
        0.75,
        1.0,
        2.5,
        5.0,
    ),
)

def init_metrics() -> None:
    # Metric objects are registered on creation in the default registry.
    return


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)

        route = "unknown"
        if request.scope.get("route") is not None:
            route_path = getattr(request.scope["route"], "path", None)
            if route_path:
                route = route_path

        status = str(response.status_code)
        method = request.method

        HTTP_REQUESTS_TOTAL.labels(method=method, path=route, status=status).inc()
        HTTP_REQUEST_DURATION.labels(method=method, path=route).observe(time.perf_counter() - start)

        logging.info("%s %s -> %s", method, request.url.path, status)
        return response
