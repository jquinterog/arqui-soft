"""
Configuración compartida (variables de entorno).
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Por defecto localhost para desarrollo local; en Docker/K8s usar env KAFKA_BOOTSTRAP_SERVERS=kafka:9092
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_ordenes: str = "ordenes"
    # DynamoDB
    dynamo_table_ordenes: str = "ordenes"
    aws_region: str = "us-east-1"
    aws_endpoint_url: str | None = None  # para Localstack o pruebas locales
    aws_access_key_id: str | None = None  # Localstack: test; AWS real: tu clave
    aws_secret_access_key: str | None = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # ignorar otras variables del .env que no estén definidas aquí


@lru_cache
def get_settings() -> Settings:
    return Settings()
