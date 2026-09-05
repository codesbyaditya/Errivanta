import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "order-service"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/servicewatch_order"
    )
    PORT: int = int(os.getenv("PORT", "8002"))
    SERVICEWATCH_API_KEY: str = os.getenv(
        "SERVICEWATCH_API_KEY",
        "sw_demo_order_key_12345"
    )
    SERVICEWATCH_URL: str = os.getenv(
        "SERVICEWATCH_URL",
        "http://localhost:8001"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()
