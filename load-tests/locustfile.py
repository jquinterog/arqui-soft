import time
import random
from locust import HttpUser, task

class HelloWorldUser(HttpUser):
    @task
    def create_order(self):
        payload = {
            "tipo": "venta",
            "activo": "string",
            "cantidad": 1,
            "precio": 1,
            "cliente_id": "string"
        }

        self.client.post(
            "/ordenes",
            json=payload,  # Automatically sets Content-Type: application/json
        )
        # random_timeout_ms = random.randint(0, 119999)
        # time.sleep(random_timeout_ms / 1000)
