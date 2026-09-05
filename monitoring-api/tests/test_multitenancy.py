import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import Organization, Service, ApiKey

from sqlalchemy.pool import StaticPool

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_tenant_data_isolation():
    # 1. Register Tenant Alpha
    res_a = client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@alpha.com",
            "password": "alphaPassword123",
            "full_name": "Alpha Admin",
            "organization_name": "Alpha Corp",
        },
    )
    token_a = res_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 2. Register Tenant Beta
    res_b = client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@beta.com",
            "password": "betaPassword123",
            "full_name": "Beta Admin",
            "organization_name": "Beta Corp",
        },
    )
    token_b = res_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 3. Alpha creates a microservice
    svc_a_res = client.post(
        "/api/v1/services/register",
        headers=headers_a,
        json={"service_name": "alpha-auth-service"},
    )
    assert svc_a_res.status_code == 201
    svc_a_id = svc_a_res.json()["service_id"]
    api_key_a = svc_a_res.json()["api_key"]

    # 4. Beta creates a microservice
    svc_b_res = client.post(
        "/api/v1/services/register",
        headers=headers_b,
        json={"service_name": "beta-billing-service"},
    )
    assert svc_b_res.status_code == 201
    svc_b_id = svc_b_res.json()["service_id"]

    # 5. Ingest event into Alpha's service
    ingest_res = client.post(
        "/api/v1/events",
        headers={"X-API-Key": api_key_a},
        json={
            "service_name": "alpha-auth-service",
            "endpoint": "/login",
            "method": "POST",
            "status_code": 200,
            "response_time_ms": 45.2,
        },
    )
    assert ingest_res.status_code == 201

    # 6. Verify Alpha sees only Alpha's service
    list_a = client.get("/api/v1/services", headers=headers_a).json()
    assert len(list_a) == 1
    assert list_a[0]["name"] == "alpha-auth-service"

    # 7. Verify Beta sees only Beta's service
    list_b = client.get("/api/v1/services", headers=headers_b).json()
    assert len(list_b) == 1
    assert list_b[0]["name"] == "beta-billing-service"

    # 8. Cross-tenant access check: Beta tries to view Alpha's service metrics
    forbidden_res = client.get(f"/api/v1/services/{svc_a_id}/metrics", headers=headers_b)
    assert forbidden_res.status_code == 404
    assert "unauthorized" in forbidden_res.json()["detail"] or "not found" in forbidden_res.json()["detail"]

    # 9. Cross-tenant events check: Beta queries events
    events_b = client.get("/api/v1/events", headers=headers_b).json()
    assert len(events_b) == 0  # Beta has 0 ingested events
