import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from errivanta import Errivanta, ServiceWatch
from errivanta.client import ErrivantaClient
from errivanta.models import TelemetryEvent


def test_telemetry_event_schema():
    event = TelemetryEvent(
        service_name="test-service",
        endpoint="/api/v1/test",
        http_method="GET",
        status_code=200,
        latency_ms=12.5,
    )
    assert event.service_name == "test-service"
    assert event.status_code == 200
    assert event.latency_ms == 12.5
    assert event.error_message is None


def test_errivanta_initialization():
    monitor = Errivanta(
        service_name="payment-service",
        api_key="test_key_123",
        monitoring_url="http://localhost:8001",
        timeout=1.5,
    )
    assert monitor.service_name == "payment-service"
    assert monitor.api_key == "test_key_123"
    assert monitor.monitoring_url == "http://localhost:8001"
    assert isinstance(monitor.client, ErrivantaClient)


def test_backward_compatibility_alias():
    monitor = ServiceWatch(
        service_name="order-service",
        api_key="test_key_456",
        monitoring_url="http://localhost:8001",
    )
    assert monitor.service_name == "order-service"
    assert isinstance(monitor, Errivanta)


def test_sdk_middleware_interception():
    app = FastAPI()
    monitor = Errivanta(
        service_name="test-service",
        api_key="test_key",
        monitoring_url="http://localhost:8001",
    )
    monitor.init_app(app)

    @app.get("/items")
    def get_items():
        return {"items": [1, 2, 3]}

    client = TestClient(app)
    response = client.get("/items")
    assert response.status_code == 200
    assert response.json() == {"items": [1, 2, 3]}


def test_sdk_error_resilience():
    # Verify that failed telemetry delivery swallows exceptions and returns False
    client = ErrivantaClient(
        api_key="test_key",
        monitoring_url="http://invalid-host-unreachable.example.com",
        timeout_seconds=0.1,
    )
    event = TelemetryEvent(
        service_name="test-service",
        endpoint="/error",
        http_method="GET",
        status_code=500,
        latency_ms=50.0,
    )
    result = client.send_event_sync(event)
    assert result is False
