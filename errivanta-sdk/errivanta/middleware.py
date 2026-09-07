import time
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from errivanta.client import ErrivantaClient
from errivanta.models import TelemetryEvent

logger = logging.getLogger("errivanta")


class ErrivantaMiddleware(BaseHTTPMiddleware):
    """
    FastAPI / Starlette middleware that intercepts every HTTP request,
    calculates execution latency, extracts response codes/errors,
    and non-blockingly dispatches a TelemetryEvent to the Errivanta Monitoring Platform.
    """

    def __init__(
        self,
        app,
        service_name: str,
        client: ErrivantaClient,
        skip_paths: Optional[List[str]] = None,
    ):
        super().__init__(app)
        self.service_name = service_name
        self.client = client
        self.skip_paths = skip_paths or ["/docs", "/openapi.json", "/health", "/favicon.ico"]

    async def dispatch(self, request: Request, call_next) -> Response:
        # Check if route is in skip_paths
        path = request.url.path
        if any(path.startswith(skipped) for skipped in self.skip_paths):
            return await call_next(request)

        start_time = time.perf_counter()
        status_code = 500
        error_message = None

        try:
            response = await call_next(request)
            status_code = response.status_code
            if status_code >= 400:
                error_message = f"HTTP {status_code} Error on {request.method} {path}"
            return response
        except Exception as exc:
            status_code = 500
            error_message = f"{type(exc).__name__}: {str(exc)}"
            raise exc
        finally:
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            event = TelemetryEvent(
                service_name=self.service_name,
                endpoint=path,
                http_method=request.method,
                status_code=status_code,
                latency_ms=round(latency_ms, 2),
                timestamp=datetime.now(timezone.utc),
                error_message=error_message,
            )

            # Fire-and-forget background dispatch via isolated thread pool (immune to ASGI task cancellations)
            self.client.send_event_background(event)


# Backward compatibility alias
ServiceWatchMiddleware = ErrivantaMiddleware

