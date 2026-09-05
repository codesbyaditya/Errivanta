import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure payment-service root is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import Base, get_db
from app.main import app


# Create an isolated in-memory SQLite engine for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Override get_db dependency to use the isolated test database
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test and drop them after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


# -------------------------------------------------------------
# Test 1: Health endpoint returns status 200 and 'healthy'
# -------------------------------------------------------------
def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


# -------------------------------------------------------------
# Test 2: Create a payment with valid payload
# -------------------------------------------------------------
def test_create_payment_success():
    payload = {
        "user_id": 1,
        "amount": 500.0,
        "currency": "INR"
    }
    response = client.post("/payments", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["id"] is not None
    assert data["user_id"] == 1
    assert data["amount"] == 500.0
    assert data["currency"] == "INR"
    assert data["status"] == "SUCCESS"
    assert "created_at" in data


# -------------------------------------------------------------
# Test 3: Retrieve an existing payment by ID
# -------------------------------------------------------------
def test_get_payment_success():
    # First, create a payment
    payload = {
        "user_id": 42,
        "amount": 1250.75,
        "currency": "USD"
    }
    create_res = client.post("/payments", json=payload)
    assert create_res.status_code == 201
    payment_id = create_res.json()["id"]

    # Now retrieve it
    get_res = client.get(f"/payments/{payment_id}")
    assert get_res.status_code == 200
    retrieved = get_res.json()
    assert retrieved["id"] == payment_id
    assert retrieved["user_id"] == 42
    assert retrieved["amount"] == 1250.75
    assert retrieved["currency"] == "USD"
    assert retrieved["status"] == "SUCCESS"


# -------------------------------------------------------------
# Test 4: Retrieve a non-existent payment returns 404
# -------------------------------------------------------------
def test_get_payment_not_found():
    response = client.get("/payments/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Payment with ID 999999 not found"


# -------------------------------------------------------------
# Test 5: Reject invalid payment (amount <= 0)
# -------------------------------------------------------------
def test_create_payment_invalid_amount():
    payload = {
        "user_id": 1,
        "amount": -50.0,
        "currency": "INR"
    }
    response = client.post("/payments", json=payload)
    # FastAPI & Pydantic automatically reject invalid input with 422 Unprocessable Entity
    assert response.status_code == 422


# -------------------------------------------------------------
# Test 6: Reject invalid payment (missing required fields)
# -------------------------------------------------------------
def test_create_payment_missing_required_fields():
    payload = {
        "amount": 500.0
        # user_id is missing!
    }
    response = client.post("/payments", json=payload)
    assert response.status_code == 422
