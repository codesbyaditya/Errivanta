import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""
    APP_NAME: str = "payment-service"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/servicewatch_payment"
    )
    SERVICEWATCH_API_KEY: str = os.getenv(
        "SERVICEWATCH_API_KEY",
        "sw_demo_payment_key_12345"
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


