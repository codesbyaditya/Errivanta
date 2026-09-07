import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
import httpx
from errivanta.models import TelemetryEvent

logger = logging.getLogger("errivanta")


class ErrivantaClient:
    """
    HTTP client responsible for dispatching telemetry events to the Errivanta Monitoring API.
    Designed with isolated background threads, persistent HTTP connection pool, strict timeouts,
    and error-swallowing to ensure customer applications never crash or experience latency.
    """

    def __init__(
        self,
        api_key: str,
        monitoring_url: str = "http://localhost:8001",
        timeout_seconds: float = 5.0,
        max_workers: int = 4,
    ):
        self.api_key = api_key
        url = monitoring_url.rstrip("/")
        for suffix in ["/api/v1/events", "/api/v1/telemetry", "/api/v1", "/telemetry", "/events"]:
            if url.endswith(suffix):
                url = url[:-len(suffix)].rstrip("/")
                break
        self.monitoring_url = url
        self.events_endpoint = f"{self.monitoring_url}/api/v1/events"
        self.timeout = timeout_seconds
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="errivanta-telemetry")
        self._sync_client = httpx.Client(timeout=self.timeout)

    def send_event_background(self, event: TelemetryEvent) -> None:
        """
        Dispatches telemetry event in an isolated background thread pool.
        Never blocks the caller and immune to ASGI/asyncio task cancellations.
        """
        try:
            self._executor.submit(self.send_event_sync, event)
        except Exception as exc:
            logger.debug(f"[Errivanta] Failed to queue background telemetry: {exc}")

    def send_event_sync(self, event: TelemetryEvent) -> bool:
        """
        Synchronously sends telemetry event via persistent connection.
        """
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
        }
        try:
            data = event.model_dump(mode="json") if hasattr(event, "model_dump") else event.dict()
            payload = {
                "service_name": data.get("service_name"),
                "endpoint": data.get("endpoint"),
                "method": data.get("method") or data.get("http_method", "GET"),
                "status_code": data.get("status_code", 200),
                "response_time_ms": data.get("response_time_ms") if data.get("response_time_ms") is not None else data.get("latency_ms", 0.0),
                "error": data.get("error") or data.get("error_message"),
                "timestamp": data.get("timestamp"),
            }
            response = self._sync_client.post(
                self.events_endpoint,
                json=payload,
                headers=headers,
            )
            if response.status_code not in (200, 201):
                logger.warning(
                    f"[Errivanta] Failed to deliver telemetry: HTTP {response.status_code} - {response.text}"
                )
                return False
            return True
        except Exception as exc:
            # Graceful degradation: Log a warning and swallow exception so customer app is unaffected
            logger.debug(f"[Errivanta] Telemetry delivery error (gracefully ignored): {exc}")
            return False

    async def send_event_async(self, event: TelemetryEvent) -> bool:
        """
        Asynchronously sends a telemetry event to the Errivanta API.
        """
        return self.send_event_sync(event)


# Backward compatibility alias
ServiceWatchClient = ErrivantaClient

