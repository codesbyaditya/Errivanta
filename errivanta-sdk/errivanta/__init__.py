from typing import Optional, List
from errivanta.client import ErrivantaClient, ServiceWatchClient
from errivanta.middleware import ErrivantaMiddleware, ServiceWatchMiddleware
from errivanta.models import TelemetryEvent

__version__ = "0.2.0"
__all__ = [
    "Errivanta",
    "ErrivantaClient",
    "ErrivantaMiddleware",
    "TelemetryEvent",
    "ServiceWatch",
    "ServiceWatchClient",
    "ServiceWatchMiddleware",
]


class Errivanta:
    """
    Main entry point for integrating Errivanta into a Python/FastAPI service.

    Example usage:
    ```python
    from fastapi import FastAPI
    from errivanta import Errivanta

    app = FastAPI()

    monitor = Errivanta(
        service_name="payment-service",
        api_key="sw_live_YOUR_KEY",
        monitoring_url="http://localhost:8001"
    )
    monitor.init_app(app)
    ```
    """

    def __init__(
        self,
        service_name: str,
        api_key: str,
        monitoring_url: str = "http://localhost:8001",
        timeout: float = 2.0,
        skip_paths: Optional[List[str]] = None,
    ):
        self.service_name = service_name
        self.api_key = api_key
        self.monitoring_url = monitoring_url.rstrip("/")
        self.skip_paths = skip_paths or []
        self.client = ErrivantaClient(
            api_key=self.api_key,
            monitoring_url=self.monitoring_url,
            timeout_seconds=timeout,
        )

    def init_app(self, app) -> None:
        """
        Attaches the Errivanta monitoring middleware to the provided FastAPI / Starlette app.
        """
        app.add_middleware(
            ErrivantaMiddleware,
            service_name=self.service_name,
            client=self.client,
            skip_paths=self.skip_paths,
        )


# Backward compatibility alias
ServiceWatch = Errivanta
