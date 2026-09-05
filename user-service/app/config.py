import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "user-service"
    PORT: int = int(os.getenv("PORT", "8003"))
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/servicewatch_user"
    )
    SERVICEWATCH_API_KEY: str = os.getenv("SERVICEWATCH_API_KEY", "sw_live_user_service_key")
    SERVICEWATCH_URL: str = os.getenv("SERVICEWATCH_URL", "http://localhost:8001/api/v1/telemetry")

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()
