import time
import random
from locust import HttpUser, task

class HelloWorldUser(HttpUser):
    @task
    def hello_world(self):
        self.client.get("/orders/")
        # random_timeout_ms = random.randint(0, 119999)
        # time.sleep(random_timeout_ms / 1000)
