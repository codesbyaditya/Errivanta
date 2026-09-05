import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import User

# In-memory test SQLite DB
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_user_service.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "user-service"


def test_create_user_success():
    payload = {
        "username": "alex_smith",
        "email": "alex@example.com",
        "full_name": "Alex Smith",
        "role": "backend_lead",
    }
    response = client.post("/users", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["username"] == "alex_smith"
    assert data["email"] == "alex@example.com"
    assert data["role"] == "backend_lead"
    assert data["status"] == "ACTIVE"


def test_create_duplicate_user():
    payload = {
        "username": "dup_user",
        "email": "dup@example.com",
        "full_name": "Duplicate Test",
    }
    res1 = client.post("/users", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/users", json=payload)
    assert res2.status_code == 400
    assert "already registered" in res2.json()["detail"]


def test_list_and_get_user():
    u1 = {"username": "user1", "email": "u1@test.com", "full_name": "User 1"}
    u2 = {"username": "user2", "email": "u2@test.com", "full_name": "User 2"}
    client.post("/users", json=u1)
    client.post("/users", json=u2)

    list_res = client.get("/users")
    assert list_res.status_code == 200
    users = list_res.json()
    assert len(users) == 2

    get_res = client.get(f"/users/{users[0]['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["username"] == "user1"


def test_simulate_failure():
    response = client.post("/users/simulate-failure")
    assert response.status_code == 500
    assert "Simulated database timeout" in response.json()["detail"]
