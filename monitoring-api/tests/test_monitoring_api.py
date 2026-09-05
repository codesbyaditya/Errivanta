import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure monitoring-api root is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import Base, get_db
from app.models import Organization, Service, ApiKey, MonitoringEvent, Incident, IncidentStatus, IncidentSeverity
from app.main import app, seed_initial_demo_data

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    seed_initial_demo_data(db)
    db.close()
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


# 1. Health Endpoint Test
def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


# 2. Register Service & Generate API Key
def test_register_service():
    payload = {
        "organization_name": "Acme Corp",
        "service_name": "billing-service",
    }
    response = client.post("/api/v1/services/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["organization_name"] == "Acme Corp"
    assert data["service_name"] == "billing-service"
    assert data["api_key"].startswith("sw_")


# 3. Ingest Event with Valid API Key
def test_ingest_event_success():
    headers = {"X-API-Key": "sw_demo_payment_key_12345"}
    event_payload = {
        "service_name": "payment-service",
        "endpoint": "/payments",
        "method": "POST",
        "status_code": 201,
        "response_time_ms": 15.4,
        "error": None,
    }
    response = client.post("/api/v1/events", json=event_payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["service_name"] == "payment-service"
    assert data["status_code"] == 201


# 4. Ingest Event Missing API Key
def test_ingest_event_missing_api_key():
    event_payload = {
        "service_name": "payment-service",
        "endpoint": "/health",
        "method": "GET",
        "status_code": 200,
        "response_time_ms": 2.1,
    }
    response = client.post("/api/v1/events", json=event_payload)
    assert response.status_code == 401


# 5. Ingest Event Invalid API Key
def test_ingest_event_invalid_api_key():
    headers = {"X-API-Key": "sw_invalid_unknown_key"}
    event_payload = {
        "service_name": "payment-service",
        "endpoint": "/health",
        "method": "GET",
        "status_code": 200,
        "response_time_ms": 2.1,
    }
    response = client.post("/api/v1/events", json=event_payload, headers=headers)
    assert response.status_code == 403


# 6. Ingest Event Invalid Payload
def test_ingest_event_invalid_payload():
    headers = {"X-API-Key": "sw_demo_payment_key_12345"}
    event_payload = {
        "service_name": "payment-service",
        "endpoint": "/payments",
        "method": "POST",
        "status_code": 9999,
        "response_time_ms": -10.0,
    }
    response = client.post("/api/v1/events", json=event_payload, headers=headers)
    assert response.status_code == 422


# 7. Dashboard Overview Endpoint
def test_dashboard_overview():
    response = client.get("/api/v1/dashboard/overview")
    assert response.status_code == 200
    data = response.json()
    assert "total_services" in data
    assert "healthy_services" in data
    assert "open_incidents" in data
    assert data["total_services"] >= 2  # payment-service & order-service seeded


# 8. List Services Endpoint
def test_list_services():
    response = client.get("/api/v1/services")
    assert response.status_code == 200
    services = response.json()
    assert len(services) >= 2
    service_names = [s["name"] for s in services]
    assert "payment-service" in service_names
    assert "order-service" in service_names


# 9. Service Metrics and Time Series Endpoint
def test_service_metrics_detail():
    headers = {"X-API-Key": "sw_demo_payment_key_12345"}
    client.post(
        "/api/v1/events",
        json={
            "service_name": "payment-service",
            "endpoint": "/payments",
            "method": "POST",
            "status_code": 200,
            "response_time_ms": 25.0,
        },
        headers=headers,
    )

    # Get payment-service id
    svc_res = client.get("/api/v1/services")
    payment_svc_id = next(s["id"] for s in svc_res.json() if s["name"] == "payment-service")

    metrics_res = client.get(f"/api/v1/services/{payment_svc_id}/metrics")
    assert metrics_res.status_code == 200
    m_data = metrics_res.json()
    assert m_data["service_name"] == "payment-service"
    assert "time_series" in m_data
    assert len(m_data["time_series"]) > 0


# 10. Automatic Incident Creation on Error Threshold Breach (>10%) & Deduplication
def test_incident_creation_and_deduplication():
    headers = {"X-API-Key": "sw_demo_payment_key_12345"}

    # Ingest 1 successful request and 9 failing requests (90% error rate -> CRITICAL threshold breach)
    client.post(
        "/api/v1/events",
        json={
            "service_name": "payment-service",
            "endpoint": "/payments",
            "method": "POST",
            "status_code": 200,
            "response_time_ms": 10.0,
        },
        headers=headers,
    )

    for _ in range(9):
        client.post(
            "/api/v1/events",
            json={
                "service_name": "payment-service",
                "endpoint": "/payments",
                "method": "POST",
                "status_code": 500,
                "response_time_ms": 100.0,
                "error": "Database connection failed",
            },
            headers=headers,
        )

    # Verify incident was created in PostgreSQL
    incidents_res = client.get("/api/v1/incidents?status=OPEN")
    assert incidents_res.status_code == 200
    incidents = incidents_res.json()
    assert len(incidents) == 1
    incident = incidents[0]
    assert incident["service_name"] == "payment-service"
    assert incident["severity"] == "CRITICAL"
    assert incident["status"] == "OPEN"
    assert incident["error_rate"] >= 10.0

    incident_id = incident["id"]

    # Send MORE errors to test deduplication
    for _ in range(5):
        client.post(
            "/api/v1/events",
            json={
                "service_name": "payment-service",
                "endpoint": "/payments",
                "method": "POST",
                "status_code": 500,
                "response_time_ms": 110.0,
                "error": "Database connection failed",
            },
            headers=headers,
        )

    # Verify NO duplicate incident was created (still exactly 1 open incident)
    incidents_res2 = client.get("/api/v1/incidents?status=OPEN")
    incidents2 = incidents_res2.json()
    assert len(incidents2) == 1
    assert incidents2[0]["id"] == incident_id


# 11. Incident Resolution Endpoint
def test_resolve_incident():
    headers = {"X-API-Key": "sw_demo_payment_key_12345"}
    # Trigger an incident with 500 errors
    client.post(
        "/api/v1/events",
        json={
            "service_name": "payment-service",
            "endpoint": "/payments",
            "method": "POST",
            "status_code": 500,
            "response_time_ms": 200.0,
            "error": "Timeout",
        },
        headers=headers,
    )

    open_incidents = client.get("/api/v1/incidents?status=OPEN").json()
    assert len(open_incidents) >= 1
    target_id = open_incidents[0]["id"]

    # Resolve incident
    res = client.patch(f"/api/v1/incidents/{target_id}/resolve")
    assert res.status_code == 200
    resolved_data = res.json()["incident"]
    assert resolved_data["status"] == "RESOLVED"
    assert resolved_data["resolved_at"] is not None

    # Check open list is now empty of this incident
    remaining_open = client.get("/api/v1/incidents?status=OPEN").json()
    assert not any(inc["id"] == target_id for inc in remaining_open)
