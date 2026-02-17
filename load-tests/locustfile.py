import time
import random
from locust import HttpUser, task

class HelloWorldUser(HttpUser):
    @task
    def create_order(self):
        payload = {
            "tipo": "venta",
            "activo": "AAPL",
            "cantidad": 5,
            "precio": 190.5,
            "cliente_id": "cli_002"
        }

        self.client.post(
            "/ordenes",
            json=payload,  # Automatically sets Content-Type: application/json
        )
        random_timeout_ms = random.randint(0, 119999)
        time.sleep(random_timeout_ms / 1000)
