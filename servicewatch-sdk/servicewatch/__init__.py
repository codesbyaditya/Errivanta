from typing import Optional, List
from servicewatch.client import ServiceWatchClient
from servicewatch.middleware import ServiceWatchMiddleware
from servicewatch.models import TelemetryEvent

__version__ = "0.1.0"
__all__ = ["ServiceWatch", "ServiceWatchClient", "ServiceWatchMiddleware", "TelemetryEvent"]


class ServiceWatch:
    """
    Main entry point for integrating ServiceWatch into a Python/FastAPI service.

    Example usage:
    ```python
    from fastapi import FastAPI
    from servicewatch import ServiceWatch

    app = FastAPI()

    monitor = ServiceWatch(
        service_name="payment-service",
        api_key="sw_demo_12345",
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
        self.client = ServiceWatchClient(
            api_key=self.api_key,
            monitoring_url=self.monitoring_url,
            timeout_seconds=timeout,
        )

    def init_app(self, app) -> None:
        """
        Attaches the ServiceWatch monitoring middleware to the provided FastAPI / Starlette app.
        """
        app.add_middleware(
            ServiceWatchMiddleware,
            service_name=self.service_name,
            client=self.client,
            skip_paths=self.skip_paths,
        )
