from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class TelemetryEvent(BaseModel):
    service_name: str = Field(..., description="Name of the service emitting the event")
    endpoint: str = Field(..., description="API endpoint/path (e.g. /payments)")
    method: str = Field(..., description="HTTP Method (GET, POST, PUT, DELETE, etc.)")
    status_code: int = Field(..., description="HTTP Response status code")
    response_time_ms: float = Field(..., description="Response latency in milliseconds")
    error: Optional[str] = Field(default=None, description="Error message or exception details if request failed")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp"
    )
