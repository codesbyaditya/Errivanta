from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class EventIngestSchema(BaseModel):
    service_name: str = Field(..., min_length=1, description="Service name matching API key registration")
    endpoint: str = Field(..., min_length=1, description="Endpoint path, e.g. /payments")
    method: str = Field(..., min_length=2, max_length=10, description="HTTP Method")
    status_code: int = Field(..., ge=100, le=599, description="HTTP response status code")
    response_time_ms: float = Field(..., ge=0, description="Response time in milliseconds")
    error: Optional[str] = Field(default=None, description="Error message if unhandled failure occurred")
    timestamp: Optional[datetime] = Field(default=None, description="Timestamp of the event")


class EventResponseSchema(BaseModel):
    id: int
    service_name: str
    endpoint: str
    method: str
    status_code: int
    response_time_ms: float
    error: Optional[str] = None
    timestamp: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceRegisterSchema(BaseModel):
    organization_name: str = Field(default="Demo Organization")
    service_name: str = Field(..., min_length=1)


class ServiceRegisterResponse(BaseModel):
    organization_id: int
    organization_name: str
    service_id: int
    service_name: str
    api_key: str

    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str = "healthy"
    service: str = "errivanta-monitoring-api"
    database: str = "connected"
    redis: str = "connected"
    version: str = "3.0.0"


# -------------------------------------------------------------
# Phase 3 Auth & Multi-Tenancy Schemas
# -------------------------------------------------------------
class UserRegisterRequest(BaseModel):
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = "Admin User"
    organization_name: str = Field(default="My Organization", min_length=2)


class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    role: str
    organization_id: int
    organization_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# -------------------------------------------------------------
# Phase 2 Schemas: Incidents, Metrics & Dashboard
# -------------------------------------------------------------
class IncidentResponseSchema(BaseModel):
    id: int
    service_id: int
    service_name: str
    severity: str
    status: str
    trigger_condition: str
    error_rate: float
    relevant_endpoint: Optional[str] = None
    description: Optional[str] = None
    started_at: datetime
    last_updated_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class IncidentResolveResponse(BaseModel):
    message: str
    incident: IncidentResponseSchema


class ServiceSummarySchema(BaseModel):
    id: int
    name: str
    organization_id: int
    health: str  # HEALTHY, WARNING, CRITICAL
    total_requests_last_5m: int
    total_errors_last_5m: int
    error_rate: float
    avg_response_time_ms: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimeSeriesPoint(BaseModel):
    minute: str
    timestamp: int
    requests: int
    errors: int
    error_rate: float
    avg_response_time_ms: float


class ServiceMetricsDetailSchema(BaseModel):
    service_id: int
    service_name: str
    health: str
    window_minutes: int
    total_requests: int
    total_errors: int
    error_rate: float
    avg_response_time_ms: float
    p95_response_time_ms: float
    recent_errors: List[dict] = []
    time_series: List[TimeSeriesPoint] = []


class DashboardOverviewResponse(BaseModel):
    total_services: int
    healthy_services: int
    warning_services: int
    critical_services: int
    open_incidents: int
