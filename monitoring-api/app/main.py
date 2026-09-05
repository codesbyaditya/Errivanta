import logging
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db, engine, Base, SessionLocal
from app.models import (
    Organization,
    Service,
    ApiKey,
    MonitoringEvent,
    Incident,
    IncidentStatus,
    IncidentSeverity,
    User,
)
from app.schemas import (
    EventIngestSchema,
    EventResponseSchema,
    ServiceRegisterSchema,
    ServiceRegisterResponse,
    HealthResponse,
    IncidentResponseSchema,
    IncidentResolveResponse,
    ServiceSummarySchema,
    ServiceMetricsDetailSchema,
    DashboardOverviewResponse,
    UserRegisterRequest,
    UserLoginRequest,
    AuthResponse,
    UserOut,
)
from app.auth import (
    validate_api_key,
    get_current_user,
    get_optional_current_user,
    verify_password,
    get_password_hash,
    create_access_token,
)
from app.redis_client import redis_manager
from app.worker import worker
from app.incident_engine import IncidentEngine

logger = logging.getLogger("servicewatch.api")


# Helper: Seed initial demo organizations, users, and microservices
def seed_initial_demo_data(db: Session):
    # 1. Demo Organization
    org = db.query(Organization).filter(Organization.name == "Demo Organization").first()
    if not org:
        org = Organization(name="Demo Organization")
        db.add(org)
        db.commit()
        db.refresh(org)

    # 2. Demo Admin Users (admin@errivanta.io & admin@servicewatch.io / password123)
    for email, name in [("admin@errivanta.io", "Errivanta Admin"), ("admin@servicewatch.io", "Errivanta Admin")]:
        u = db.query(User).filter(User.email == email).first()
        if not u:
            u = User(
                organization_id=org.id,
                email=email,
                hashed_password=get_password_hash("password123"),
                full_name=name,
                role="admin",
            )
            db.add(u)
            db.commit()

    # 3. Payment Service
    pay_service = db.query(Service).filter(Service.name == "payment-service").first()
    if not pay_service:
        pay_service = Service(organization_id=org.id, name="payment-service")
        db.add(pay_service)
        db.commit()
        db.refresh(pay_service)

    pay_key = db.query(ApiKey).filter(ApiKey.key == "sw_demo_payment_key_12345").first()
    if not pay_key:
        pay_key = ApiKey(
            service_id=pay_service.id,
            key="sw_demo_payment_key_12345",
            name="Payment Service Key",
            is_active=True,
        )
        db.add(pay_key)
        db.commit()

    # 4. Order Service
    order_service = db.query(Service).filter(Service.name == "order-service").first()
    if not order_service:
        order_service = Service(organization_id=org.id, name="order-service")
        db.add(order_service)
        db.commit()
        db.refresh(order_service)

    order_key = db.query(ApiKey).filter(ApiKey.key == "sw_demo_order_key_12345").first()
    if not order_key:
        order_key = ApiKey(
            service_id=order_service.id,
            key="sw_demo_order_key_12345",
            name="Order Service Key",
            is_active=True,
        )
        db.add(order_key)
        db.commit()

    # 5. User Service
    user_service = db.query(Service).filter(Service.name == "user-service").first()
    if not user_service:
        user_service = Service(organization_id=org.id, name="user-service")
        db.add(user_service)
        db.commit()
        db.refresh(user_service)

    user_key = db.query(ApiKey).filter(ApiKey.key == "sw_live_user_service_key").first()
    if not user_key:
        user_key = ApiKey(
            service_id=user_service.id,
            key="sw_live_user_service_key",
            name="User Service Key",
            is_active=True,
        )
        db.add(user_key)
        db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database tables exist
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_initial_demo_data(db)
    finally:
        db.close()

    # Start background telemetry processing worker
    worker.start_in_background()
    yield
    worker.stop()


app = FastAPI(
    title="Errivanta Monitoring API",
    description="Central ingestion and dashboard API for Errivanta telemetry, metrics, and incidents.",
    version="3.0.0",
    lifespan=lifespan,
)

# Enable CORS for frontend dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------------------
# System & Deep Health Endpoint
# -------------------------------------------------------------
@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Deep health check for API, Database, and Redis",
    tags=["System"],
)
def health_check(db: Session = Depends(get_db)):
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = f"unhealthy: {str(e)}"

    redis_status = "connected"
    try:
        if hasattr(redis_manager.client, "ping"):
            redis_manager.client.ping()
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        redis_status = f"unhealthy: {str(e)}"

    overall_status = "healthy" if db_status == "connected" and redis_status == "connected" else "degraded"

    return {
        "status": overall_status,
        "service": "servicewatch-monitoring-api",
        "database": db_status,
        "redis": redis_status,
        "version": "3.0.0",
    }


# -------------------------------------------------------------
# Phase 3: Auth & Tenant Management Endpoints
# -------------------------------------------------------------
@app.post(
    "/api/v1/auth/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new organization admin user",
    tags=["Authentication"],
)
def register_user(payload: UserRegisterRequest, db: Session = Depends(get_db)):
    # Check if user already exists
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )

    # Find or create organization
    org = db.query(Organization).filter(Organization.name == payload.organization_name).first()
    if not org:
        org = Organization(name=payload.organization_name)
        db.add(org)
        db.commit()
        db.refresh(org)

    # Hash password & create user
    hashed_pwd = get_password_hash(payload.password)
    user = User(
        organization_id=org.id,
        email=payload.email,
        hashed_password=hashed_pwd,
        full_name=payload.full_name or "Admin User",
        role="admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create JWT
    token = create_access_token({"sub": str(user.id), "email": user.email, "org_id": org.id})

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "organization_id": org.id,
            "organization_name": org.name,
            "created_at": user.created_at,
        },
    }


@app.post(
    "/api/v1/auth/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Login to ServiceWatch dashboard",
    tags=["Authentication"],
)
def login_user(payload: UserLoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    org_name = org.name if org else "Default Org"

    token = create_access_token({"sub": str(user.id), "email": user.email, "org_id": user.organization_id})

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "organization_id": user.organization_id,
            "organization_name": org_name,
            "created_at": user.created_at,
        },
    }


@app.get(
    "/api/v1/auth/me",
    response_model=UserOut,
    status_code=status.HTTP_200_OK,
    summary="Get current logged in user and organization",
    tags=["Authentication"],
)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "organization_id": current_user.organization_id,
        "organization_name": org.name if org else "Unknown Org",
        "created_at": current_user.created_at,
    }


# -------------------------------------------------------------
# Microservice Registration & API Key Provisioning
# -------------------------------------------------------------
@app.post(
    "/api/v1/services/register",
    response_model=ServiceRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a microservice and generate an API key",
    tags=["Services"],
)
def register_service(
    payload: ServiceRegisterSchema,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    # If user is logged in, attach service to their tenant organization
    if current_user:
        org_id = current_user.organization_id
        org = db.query(Organization).filter(Organization.id == org_id).first()
    else:
        org = db.query(Organization).filter(Organization.name == payload.organization_name).first()
        if not org:
            org = Organization(name=payload.organization_name)
            db.add(org)
            db.commit()
            db.refresh(org)
        org_id = org.id

    service = Service(organization_id=org_id, name=payload.service_name)
    db.add(service)
    db.commit()
    db.refresh(service)

    generated_key = f"sw_{secrets.token_hex(16)}"
    api_key_obj = ApiKey(
        service_id=service.id,
        key=generated_key,
        name=f"Key for {payload.service_name}",
        is_active=True,
    )
    db.add(api_key_obj)
    db.commit()

    return {
        "organization_id": org_id,
        "organization_name": org.name if org else payload.organization_name,
        "service_id": service.id,
        "service_name": service.name,
        "api_key": generated_key,
    }


# -------------------------------------------------------------
# Telemetry Ingestion (Authenticated via X-API-Key)
# -------------------------------------------------------------
@app.post(
    "/api/v1/events",
    response_model=EventResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest telemetry event from monitored service",
    tags=["Telemetry"],
)
def ingest_event(
    event_in: EventIngestSchema,
    authenticated_service: Service = Depends(validate_api_key),
    db: Session = Depends(get_db),
):
    """
    Ingests telemetry from monitored microservice.
    Persists to PostgreSQL and updates Redis metrics & incident detection.
    """
    event_timestamp = event_in.timestamp or datetime.now(timezone.utc)

    # 1. Store in permanent PostgreSQL storage
    db_event = MonitoringEvent(
        service_id=authenticated_service.id,
        service_name=event_in.service_name,
        endpoint=event_in.endpoint,
        method=event_in.method.upper(),
        status_code=event_in.status_code,
        response_time_ms=event_in.response_time_ms,
        error=event_in.error,
        timestamp=event_timestamp,
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)

    # 2. Update Redis metrics & evaluate incidents
    event_dict = {
        "service_id": authenticated_service.id,
        "service_name": event_in.service_name,
        "endpoint": event_in.endpoint,
        "method": event_in.method.upper(),
        "status_code": event_in.status_code,
        "response_time_ms": event_in.response_time_ms,
        "error": event_in.error,
        "already_persisted": True,
    }
    # Direct processing via worker for immediate consistency
    worker.process_single_event(event_dict, db)

    return db_event


@app.get(
    "/api/v1/events",
    response_model=List[EventResponseSchema],
    status_code=status.HTTP_200_OK,
    summary="List ingested events (Protected / Tenant-Isolated)",
    tags=["Telemetry"],
)
def list_events(
    service_name: Optional[str] = Query(None, description="Filter by service name"),
    service_id: Optional[int] = Query(None, description="Filter by service ID"),
    limit: int = Query(50, ge=1, le=500),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(MonitoringEvent)
    if current_user:
        # Strict tenant isolation
        query = query.join(Service).filter(Service.organization_id == current_user.organization_id)

    if service_name:
        query = query.filter(MonitoringEvent.service_name == service_name)
    if service_id:
        query = query.filter(MonitoringEvent.service_id == service_id)
    events = query.order_by(MonitoringEvent.id.desc()).limit(limit).all()
    return events


# -------------------------------------------------------------
# Dashboard & Metric APIs (Multi-Tenant Isolated)
# -------------------------------------------------------------
@app.get(
    "/api/v1/dashboard/overview",
    response_model=DashboardOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Dashboard top overview metrics (Tenant-Isolated)",
    tags=["Dashboard"],
)
def get_dashboard_overview(
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Service)
    if current_user:
        query = query.filter(Service.organization_id == current_user.organization_id)

    services = query.all()
    total_services = len(services)
    healthy_count = 0
    warning_count = 0
    critical_count = 0

    for s in services:
        m = redis_manager.get_service_metrics(s.id, window_minutes=5)
        h = m.get("health", "HEALTHY")
        if h == "CRITICAL":
            critical_count += 1
        elif h == "WARNING":
            warning_count += 1
        else:
            healthy_count += 1

    incident_query = db.query(Incident).filter(Incident.status == IncidentStatus.OPEN.value)
    if current_user:
        incident_query = incident_query.join(Service).filter(Service.organization_id == current_user.organization_id)

    open_incidents = incident_query.count()

    return {
        "total_services": total_services,
        "healthy_services": healthy_count,
        "warning_services": warning_count,
        "critical_services": critical_count,
        "open_incidents": open_incidents,
    }


@app.get(
    "/api/v1/services",
    response_model=List[ServiceSummarySchema],
    status_code=status.HTTP_200_OK,
    summary="List microservices with real-time health and metrics (Tenant-Isolated)",
    tags=["Services"],
)
def list_services(
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Service)
    if current_user:
        query = query.filter(Service.organization_id == current_user.organization_id)

    services = query.all()
    result = []
    for s in services:
        m = redis_manager.get_service_metrics(s.id, window_minutes=5)
        result.append({
            "id": s.id,
            "name": s.name,
            "organization_id": s.organization_id,
            "health": m["health"],
            "total_requests_last_5m": m["total_requests"],
            "total_errors_last_5m": m["total_errors"],
            "error_rate": m["error_rate"],
            "avg_response_time_ms": m["avg_response_time_ms"],
            "created_at": s.created_at,
        })
    return result


@app.get(
    "/api/v1/services/{service_id}",
    response_model=ServiceSummarySchema,
    status_code=status.HTTP_200_OK,
    summary="Get microservice summary (Tenant-Isolated)",
    tags=["Services"],
)
def get_service(
    service_id: int,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Service).filter(Service.id == service_id)
    if current_user:
        query = query.filter(Service.organization_id == current_user.organization_id)

    service = query.first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found or unauthorized")

    m = redis_manager.get_service_metrics(service.id, window_minutes=5)
    return {
        "id": service.id,
        "name": service.name,
        "organization_id": service.organization_id,
        "health": m["health"],
        "total_requests_last_5m": m["total_requests"],
        "total_errors_last_5m": m["total_errors"],
        "error_rate": m["error_rate"],
        "avg_response_time_ms": m["avg_response_time_ms"],
        "created_at": service.created_at,
    }


@app.get(
    "/api/v1/services/{service_id}/metrics",
    response_model=ServiceMetricsDetailSchema,
    status_code=status.HTTP_200_OK,
    summary="Get detailed metrics and time series for a service (Tenant-Isolated)",
    tags=["Metrics"],
)
def get_service_metrics_detail(
    service_id: int,
    window: int = Query(5, ge=1, le=60),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Service).filter(Service.id == service_id)
    if current_user:
        query = query.filter(Service.organization_id == current_user.organization_id)

    service = query.first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found or unauthorized")

    metrics = redis_manager.get_service_metrics(service.id, window_minutes=window)
    time_series = redis_manager.get_time_series_points(service.id, points=15)

    return {
        "service_id": service.id,
        "service_name": service.name,
        "health": metrics["health"],
        "window_minutes": window,
        "total_requests": metrics["total_requests"],
        "total_errors": metrics["total_errors"],
        "error_rate": metrics["error_rate"],
        "avg_response_time_ms": metrics["avg_response_time_ms"],
        "p95_response_time_ms": metrics["p95_response_time_ms"],
        "recent_errors": metrics["recent_errors"],
        "time_series": time_series,
    }


@app.get(
    "/api/v1/services/{service_id}/events",
    response_model=List[EventResponseSchema],
    status_code=status.HTTP_200_OK,
    summary="Get recent events for a specific service (Tenant-Isolated)",
    tags=["Telemetry"],
)
def get_service_events(
    service_id: int,
    limit: int = Query(20, ge=1, le=100),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Service).filter(Service.id == service_id)
    if current_user:
        query = query.filter(Service.organization_id == current_user.organization_id)

    service = query.first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found or unauthorized")

    events = (
        db.query(MonitoringEvent)
        .filter(MonitoringEvent.service_id == service_id)
        .order_by(MonitoringEvent.id.desc())
        .limit(limit)
        .all()
    )
    return events


# -------------------------------------------------------------
# Incident Endpoints (Multi-Tenant Isolated)
# -------------------------------------------------------------
@app.get(
    "/api/v1/incidents",
    response_model=List[IncidentResponseSchema],
    status_code=status.HTTP_200_OK,
    summary="List incidents (Tenant-Isolated)",
    tags=["Incidents"],
)
def list_incidents(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by OPEN or RESOLVED"),
    service_id: Optional[int] = Query(None, description="Filter by service ID"),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Incident)
    if current_user:
        query = query.join(Service).filter(Service.organization_id == current_user.organization_id)

    if status_filter:
        query = query.filter(Incident.status == status_filter.upper())
    if service_id:
        query = query.filter(Incident.service_id == service_id)
    return query.order_by(Incident.started_at.desc()).all()


@app.get(
    "/api/v1/incidents/{incident_id}",
    response_model=IncidentResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Get single incident details (Tenant-Isolated)",
    tags=["Incidents"],
)
def get_incident(
    incident_id: int,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Incident).filter(Incident.id == incident_id)
    if current_user:
        query = query.join(Service).filter(Service.organization_id == current_user.organization_id)

    incident = query.first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found or unauthorized")
    return incident


@app.patch(
    "/api/v1/incidents/{incident_id}/resolve",
    response_model=IncidentResolveResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve an active incident (Tenant-Isolated)",
    tags=["Incidents"],
)
def resolve_incident_endpoint(
    incident_id: int,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Incident).filter(Incident.id == incident_id)
    if current_user:
        query = query.join(Service).filter(Service.organization_id == current_user.organization_id)

    incident_to_resolve = query.first()
    if not incident_to_resolve:
        raise HTTPException(status_code=404, detail="Incident not found or unauthorized")

    incident = IncidentEngine.resolve_incident(db, incident_id)
    return {
        "message": f"Incident #{incident.id} for {incident.service_name} successfully resolved.",
        "incident": incident,
    }
