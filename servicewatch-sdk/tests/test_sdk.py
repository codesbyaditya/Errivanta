import pytest
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from servicewatch import ServiceWatch
from servicewatch.client import ServiceWatchClient
from servicewatch.models import TelemetryEvent


# 1. Test Telemetry Event Model
def test_telemetry_event_model():
    event = TelemetryEvent(
        service_name="payment-service",
        endpoint="/payments",
        method="POST",
        status_code=201,
        response_time_ms=12.5,
        error=None,
    )
    assert event.service_name == "payment-service"
    assert event.endpoint == "/payments"
    assert event.status_code == 201
    assert event.response_time_ms == 12.5
    assert event.error is None
    assert event.timestamp is not None


# 2. Test Client Resilience on Unreachable Server
@pytest.mark.asyncio
async def test_client_graceful_failure_unreachable_server():
    client = ServiceWatchClient(
        api_key="sw_test_key",
        monitoring_url="http://127.0.0.1:59999",  # Non-existent port
        timeout_seconds=0.1,
    )
    event = TelemetryEvent(
        service_name="payment-service",
        endpoint="/health",
        method="GET",
        status_code=200,
        response_time_ms=5.0,
    )

    # Should safely return False without raising an exception
    success = await client.send_event_async(event)
    assert success is False

    # Sync client should also fail gracefully
    success_sync = client.send_event_sync(event)
    assert success_sync is False


# 3. Test Middleware Interception & Telemetry Recording
def test_middleware_captures_successful_requests():
    captured_events = []

    # Mock client to record events
    class MockClient(ServiceWatchClient):
        def __init__(self):
            super().__init__(api_key="sw_mock", monitoring_url="http://localhost:8001")

        async def send_event_async(self, event: TelemetryEvent) -> bool:
            captured_events.append(event)
            return True

    app = FastAPI()
    mock_client = MockClient()

    monitor = ServiceWatch(
        service_name="test-service",
        api_key="sw_mock",
    )
    monitor.client = mock_client
    monitor.init_app(app)

    @app.get("/items")
    def get_items():
        return {"items": [1, 2, 3]}

    client = TestClient(app)
    response = client.get("/items")

    assert response.status_code == 200
    assert response.json() == {"items": [1, 2, 3]}

    # Verify event was captured
    assert len(captured_events) == 1
    event = captured_events[0]
    assert event.service_name == "test-service"
    assert event.endpoint == "/items"
    assert event.method == "GET"
    assert event.status_code == 200
    assert event.response_time_ms >= 0
    assert event.error is None


# 4. Test Middleware Capturing Application Errors
def test_middleware_captures_unhandled_exceptions():
    captured_events = []

    class MockClient(ServiceWatchClient):
        def __init__(self):
            super().__init__(api_key="sw_mock", monitoring_url="http://localhost:8001")

        async def send_event_async(self, event: TelemetryEvent) -> bool:
            captured_events.append(event)
            return True

    app = FastAPI()
    mock_client = MockClient()

    monitor = ServiceWatch(service_name="test-service", api_key="sw_mock")
    monitor.client = mock_client
    monitor.init_app(app)

    @app.get("/crash")
    def crash_endpoint():
        raise RuntimeError("Simulated Database Crash")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/crash")

    assert response.status_code == 500
    assert len(captured_events) == 1
    event = captured_events[0]
    assert event.status_code == 500
    assert "RuntimeError: Simulated Database Crash" in event.error


# 5. Test Skip Paths
def test_middleware_skips_configured_paths():
    captured_events = []

    class MockClient(ServiceWatchClient):
        async def send_event_async(self, event: TelemetryEvent) -> bool:
            captured_events.append(event)
            return True

    app = FastAPI()
    monitor = ServiceWatch(
        service_name="test-service",
        api_key="sw_mock",
        skip_paths=["/internal/health"],
    )
    monitor.client = MockClient(api_key="sw_mock")
    monitor.init_app(app)

    @app.get("/internal/health")
    def health():
        return {"status": "ok"}

    client = TestClient(app)
    response = client.get("/internal/health")

    assert response.status_code == 200
    # Nothing should have been recorded for skipped path
    assert len(captured_events) == 0
