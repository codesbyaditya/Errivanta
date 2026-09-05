import asyncio
import time
from datetime import datetime, timezone
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from servicewatch.client import ServiceWatchClient
from servicewatch.models import TelemetryEvent


class ServiceWatchMiddleware(BaseHTTPMiddleware):
    """
    FastAPI / Starlette Middleware that automatically captures and transmits
    request, response, error, and latency metrics to the ServiceWatch platform.
    """

    def __init__(
        self,
        app,
        service_name: str,
        client: ServiceWatchClient,
        skip_paths: Optional[list] = None,
    ):
        super().__init__(app)
        self.service_name = service_name
        self.client = client
        self.skip_paths = skip_paths or []

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Check if the requested path should be ignored (e.g. internal health or docs)
        path = request.url.path
        if path in self.skip_paths:
            return await call_next(request)

        method = request.method
        start_time = time.perf_counter()
        iso_timestamp = datetime.now(timezone.utc).isoformat()
        status_code = 500
        error_message: Optional[str] = None

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            # Capture real unhandled application exception
            error_message = f"{type(exc).__name__}: {str(exc)}"
            status_code = 500
            raise exc
        finally:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

            telemetry_event = TelemetryEvent(
                service_name=self.service_name,
                endpoint=path,
                method=method,
                status_code=status_code,
                response_time_ms=elapsed_ms,
                error=error_message,
                timestamp=iso_timestamp,
            )

            # Fire-and-forget async delivery: execute without blocking response return
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.client.send_event_async(telemetry_event))
                else:
                    await self.client.send_event_async(telemetry_event)
            except Exception:
                # Middleware must never crash the host application
                pass
