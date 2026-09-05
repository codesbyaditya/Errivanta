import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import Organization, User
from app.auth import get_password_hash

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


def test_user_registration_success():
    payload = {
        "email": "sarah@acme.com",
        "password": "strongPassword123",
        "full_name": "Sarah Connor",
        "organization_name": "Acme Corp",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "sarah@acme.com"
    assert data["user"]["organization_name"] == "Acme Corp"


def test_user_registration_duplicate_email():
    payload = {
        "email": "sarah@acme.com",
        "password": "strongPassword123",
        "organization_name": "Acme Corp",
    }
    res1 = client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


def test_user_login_success():
    # Register user first
    payload = {
        "email": "john@acme.com",
        "password": "mySecurePassword456",
        "organization_name": "Acme Corp",
    }
    client.post("/api/v1/auth/register", json=payload)

    # Login
    login_payload = {
        "email": "john@acme.com",
        "password": "mySecurePassword456",
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "john@acme.com"


def test_user_login_invalid_password():
    payload = {
        "email": "john@acme.com",
        "password": "mySecurePassword456",
        "organization_name": "Acme Corp",
    }
    client.post("/api/v1/auth/register", json=payload)

    # Invalid password
    login_payload = {
        "email": "john@acme.com",
        "password": "wrongPassword",
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_get_me_with_valid_jwt():
    # Register user
    payload = {
        "email": "alice@acme.com",
        "password": "secretPassword789",
        "full_name": "Alice Wonderland",
        "organization_name": "Acme Wonderland",
    }
    reg_res = client.post("/api/v1/auth/register", json=payload)
    token = reg_res.json()["access_token"]

    # Call /auth/me
    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    data = me_res.json()
    assert data["email"] == "alice@acme.com"
    assert data["organization_name"] == "Acme Wonderland"


def test_get_me_without_jwt_fails():
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
