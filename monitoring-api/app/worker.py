import logging
import time
import threading
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MonitoringEvent, Service
from app.redis_client import redis_manager
from app.incident_engine import IncidentEngine

logger = logging.getLogger("servicewatch.worker")


class TelemetryBackgroundWorker:
    """
    Background worker that consumes telemetry events from the Redis queue,
    updates rolling Redis metrics, persists events to PostgreSQL, and evaluates incident thresholds.
    """

    def __init__(self, poll_interval: float = 0.5):
        self.poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def process_single_event(self, event_data: dict, db: Session):
        service_id = event_data.get("service_id")
        service_name = event_data.get("service_name")
        endpoint = event_data.get("endpoint")
        method = event_data.get("method")
        status_code = event_data.get("status_code", 200)
        response_time_ms = float(event_data.get("response_time_ms", 0.0))
        error = event_data.get("error")

        # 1. Update fast short-term Redis metrics
        redis_manager.record_event_metrics(
            service_id=service_id,
            status_code=status_code,
            response_time_ms=response_time_ms,
            endpoint=endpoint,
            error=error,
        )

        # 2. Persist to PostgreSQL if not already saved
        if not event_data.get("already_persisted", False):
            db_event = MonitoringEvent(
                service_id=service_id,
                service_name=service_name,
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                response_time_ms=response_time_ms,
                error=error,
                timestamp=datetime.now(timezone.utc),
            )
            db.add(db_event)
            db.commit()

        # 3. Pull fresh metrics from Redis & Evaluate Incident Detection
        fresh_metrics = redis_manager.get_service_metrics(service_id, window_minutes=5)
        IncidentEngine.evaluate_service_health_and_incidents(
            db=db,
            service_id=service_id,
            service_name=service_name,
            metrics=fresh_metrics,
            latest_endpoint=endpoint,
            latest_error=error,
        )

    def run_worker_loop(self):
        logger.info("[Worker] Telemetry background worker started.")
        self._running = True

        while self._running:
            try:
                event_data = redis_manager.dequeue_event(timeout=1)
                if event_data:
                    db = SessionLocal()
                    try:
                        self.process_single_event(event_data, db)
                    finally:
                        db.close()
                else:
                    time.sleep(self.poll_interval)
            except Exception as exc:
                logger.error(f"[Worker] Error in worker processing loop: {exc}")
                time.sleep(1.0)

    def start_in_background(self):
        """Starts worker in a background daemon thread."""
        if not self._running:
            self._thread = threading.Thread(target=self.run_worker_loop, daemon=True)
            self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)


# Global worker instance
worker = TelemetryBackgroundWorker()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Starting ServiceWatch Standalone Background Worker...")
    w = TelemetryBackgroundWorker()
    w.run_worker_loop()
