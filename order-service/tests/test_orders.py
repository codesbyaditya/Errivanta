import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure order-service root is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import Base, get_db
from app.main import app

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


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_order_service_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_create_order_success():
    payload = {
        "customer_name": "Alice Wonderland",
        "item_count": 3,
        "total_amount": 149.99,
    }
    response = client.post("/orders", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["customer_name"] == "Alice Wonderland"
    assert data["item_count"] == 3
    assert data["total_amount"] == 149.99
    assert data["status"] == "CONFIRMED"


def test_get_order_by_id():
    payload = {
        "customer_name": "Bob Builder",
        "item_count": 1,
        "total_amount": 49.50,
    }
    create_res = client.post("/orders", json=payload)
    order_id = create_res.json()["id"]

    get_res = client.get(f"/orders/{order_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["id"] == order_id
    assert data["customer_name"] == "Bob Builder"


def test_get_order_not_found():
    response = client.get("/orders/999999")
    assert response.status_code == 404
