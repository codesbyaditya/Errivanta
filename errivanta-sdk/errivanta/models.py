from datetime import datetime, timezone
from typing import Dict, Optional, Any
from pydantic import BaseModel, Field


class TelemetryEvent(BaseModel):
    """
    Schema for telemetry event payload dispatched by Errivanta SDK.
    """
    service_name: str
    endpoint: str
    http_method: str
    status_code: int
    latency_ms: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error_message: Optional[str] = None
    extra_metadata: Dict[str, Any] = Field(default_factory=dict)
