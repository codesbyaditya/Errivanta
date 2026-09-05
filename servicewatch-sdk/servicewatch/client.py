import logging
from typing import Optional
import httpx
from servicewatch.models import TelemetryEvent

logger = logging.getLogger("servicewatch")


class ServiceWatchClient:
    """
    HTTP client responsible for dispatching telemetry events to the ServiceWatch Monitoring API.
    Designed with strict timeouts and error-swallowing to ensure customer applications never crash.
    """

    def __init__(
        self,
        api_key: str,
        monitoring_url: str = "http://localhost:8001",
        timeout_seconds: float = 2.0,
    ):
        self.api_key = api_key
        self.monitoring_url = monitoring_url.rstrip("/")
        self.events_endpoint = f"{self.monitoring_url}/api/v1/events"
        self.timeout = timeout_seconds

    async def send_event_async(self, event: TelemetryEvent) -> bool:
        """
        Asynchronously sends a telemetry event to the ServiceWatch API.
        Returns True if successful, False if failed. Never raises exceptions.
        """
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.events_endpoint,
                    json=event.model_dump(),
                    headers=headers,
                )
                if response.status_code not in (200, 201):
                    logger.warning(
                        f"[ServiceWatch] Failed to deliver telemetry: HTTP {response.status_code} - {response.text}"
                    )
                    return False
                return True
        except Exception as exc:
            # Graceful degradation: Log a warning and swallow exception so customer app is unaffected
            logger.warning(f"[ServiceWatch] Telemetry delivery error (gracefully ignored): {exc}")
            return False

    def send_event_sync(self, event: TelemetryEvent) -> bool:
        """
        Synchronous fallback for sending telemetry events.
        """
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self.events_endpoint,
                    json=event.model_dump(),
                    headers=headers,
                )
                return response.status_code in (200, 201)
        except Exception as exc:
            logger.warning(f"[ServiceWatch] Telemetry delivery error (gracefully ignored): {exc}")
            return False
