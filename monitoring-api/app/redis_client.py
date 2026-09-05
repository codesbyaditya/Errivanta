import json
import logging
import os
import time
from typing import Dict, List, Optional, Tuple

import redis
try:
    import fakeredis
except ImportError:
    fakeredis = None

logger = logging.getLogger("servicewatch.redis")


class RedisMetricsManager:
    """
    Manages fast, temporary monitoring metrics, rolling time windows, and event streaming via Redis.
    Falls back gracefully to FakeRedis if a real Redis server is unreachable.
    """

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.queue_name = "servicewatch:events:queue"
        self.ttl_seconds = 1800  # 30-minute window data retention

        self.client = self._init_client()

    def _init_client(self):
        try:
            client = redis.Redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=0.5,
                socket_connect_timeout=0.5,
            )
            client.ping()
            logger.info("[Redis] Connected to live Redis instance.")
            return client
        except Exception as exc:
            logger.warning(f"[Redis] Live Redis unavailable ({exc}). Using isolated in-memory Redis engine.")
            if fakeredis:
                return fakeredis.FakeRedis(decode_responses=True)
            # Fallback simple client
            return redis.Redis(decode_responses=True)

    # -------------------------------------------------------------
    # Queue Operations for Background Worker
    # -------------------------------------------------------------
    def enqueue_event(self, event_data: dict) -> bool:
        """Pushes an incoming event onto the Redis event queue for async processing."""
        try:
            self.client.rpush(self.queue_name, json.dumps(event_data))
            return True
        except Exception as exc:
            logger.error(f"[Redis] Failed to enqueue event: {exc}")
            return False

    def dequeue_event(self, timeout: int = 1) -> Optional[dict]:
        """Pops an event from the queue for worker processing."""
        try:
            item = self.client.blpop(self.queue_name, timeout=timeout)
            if item:
                # item is tuple (queue_name, data)
                return json.loads(item[1])
            return None
        except Exception as exc:
            logger.error(f"[Redis] Failed to dequeue event: {exc}")
            return None

    # -------------------------------------------------------------
    # Fast Metric Aggregation (Counters & Rolling Windows)
    # -------------------------------------------------------------
    def record_event_metrics(
        self,
        service_id: int,
        status_code: int,
        response_time_ms: float,
        endpoint: str,
        error: Optional[str] = None,
    ):
        """
        Updates short-term counters in 1-minute buckets with automatic TTL.
        """
        now = int(time.time())
        current_minute = now // 60
        pipe = self.client.pipeline()

        req_key = f"sw:svc:{service_id}:req:{current_minute}"
        err_key = f"sw:svc:{service_id}:err:{current_minute}"
        lat_sum_key = f"sw:svc:{service_id}:lat_sum:{current_minute}"
        lat_list_key = f"sw:svc:{service_id}:recent_latencies"
        err_list_key = f"sw:svc:{service_id}:recent_errors"

        # 1. Total Requests
        pipe.incr(req_key)
        pipe.expire(req_key, self.ttl_seconds)

        # 2. Total Errors (4xx/5xx)
        if status_code >= 400 or error is not None:
            pipe.incr(err_key)
            pipe.expire(err_key, self.ttl_seconds)

            # Store recent error message
            err_msg = error or f"HTTP {status_code} on {endpoint}"
            pipe.lpush(err_list_key, json.dumps({"error": err_msg, "endpoint": endpoint, "timestamp": now}))
            pipe.ltrim(err_list_key, 0, 19)  # Keep latest 20 errors
            pipe.expire(err_list_key, self.ttl_seconds)

        # 3. Response time accumulation
        pipe.incrbyfloat(lat_sum_key, response_time_ms)
        pipe.expire(lat_sum_key, self.ttl_seconds)

        # 4. Recent latencies for p95
        pipe.lpush(lat_list_key, response_time_ms)
        pipe.ltrim(lat_list_key, 0, 99)  # Keep latest 100 samples
        pipe.expire(lat_list_key, self.ttl_seconds)

        # 5. Global lifetime counters for quick summary
        pipe.incr(f"sw:svc:{service_id}:total_requests")
        if status_code >= 400 or error is not None:
            pipe.incr(f"sw:svc:{service_id}:total_errors")

        try:
            pipe.execute()
        except Exception as exc:
            logger.error(f"[Redis] Error recording event metrics: {exc}")

    def get_service_metrics(self, service_id: int, window_minutes: int = 5) -> Dict:
        """
        Calculates aggregate request count, error count, error rate %, and latency over rolling window.
        """
        now = int(time.time())
        current_minute = now // 60

        total_requests = 0
        total_errors = 0
        total_latency_sum = 0.0

        for i in range(window_minutes):
            m = current_minute - i
            req_count = int(self.client.get(f"sw:svc:{service_id}:req:{m}") or 0)
            err_count = int(self.client.get(f"sw:svc:{service_id}:err:{m}") or 0)
            lat_sum = float(self.client.get(f"sw:svc:{service_id}:lat_sum:{m}") or 0.0)

            total_requests += req_count
            total_errors += err_count
            total_latency_sum += lat_sum

        error_rate = 0.0
        if total_requests > 0:
            error_rate = round((total_errors / total_requests) * 100, 2)

        avg_latency = 0.0
        if total_requests > 0:
            avg_latency = round(total_latency_sum / total_requests, 2)

        # Calculate p95 latency from recent samples
        p95_latency = avg_latency
        try:
            samples = self.client.lrange(f"sw:svc:{service_id}:recent_latencies", 0, -1)
            if samples:
                float_samples = sorted([float(s) for s in samples])
                idx = int(len(float_samples) * 0.95)
                p95_latency = round(float_samples[min(idx, len(float_samples) - 1)], 2)
        except Exception:
            pass

        # Calculate health status
        health = self.evaluate_health_status(error_rate, total_requests)

        # Fetch recent errors
        recent_errors = []
        try:
            raw_errs = self.client.lrange(f"sw:svc:{service_id}:recent_errors", 0, 4)
            for re in raw_errs:
                recent_errors.append(json.loads(re))
        except Exception:
            pass

        return {
            "service_id": service_id,
            "window_minutes": window_minutes,
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate": error_rate,
            "avg_response_time_ms": avg_latency,
            "p95_response_time_ms": p95_latency,
            "health": health,
            "recent_errors": recent_errors,
        }

    def get_time_series_points(self, service_id: int, points: int = 15) -> List[Dict]:
        """
        Generates 1-minute time-series metric points for charting in the dashboard.
        """
        now = int(time.time())
        current_minute = now // 60
        series = []

        for i in reversed(range(points)):
            m = current_minute - i
            minute_timestamp = m * 60
            req_count = int(self.client.get(f"sw:svc:{service_id}:req:{m}") or 0)
            err_count = int(self.client.get(f"sw:svc:{service_id}:err:{m}") or 0)
            lat_sum = float(self.client.get(f"sw:svc:{service_id}:lat_sum:{m}") or 0.0)

            rate = round((err_count / req_count * 100), 2) if req_count > 0 else 0.0
            avg_lat = round(lat_sum / req_count, 2) if req_count > 0 else 0.0

            series.append({
                "minute": time.strftime("%H:%M", time.localtime(minute_timestamp)),
                "timestamp": minute_timestamp,
                "requests": req_count,
                "errors": err_count,
                "error_rate": rate,
                "avg_response_time_ms": avg_lat,
            })

        return series

    @staticmethod
    def evaluate_health_status(error_rate: float, total_requests: int) -> str:
        """
        Evaluates health state according to configurable threshold rules:
        - error_rate < 5% -> HEALTHY
        - 5% <= error_rate <= 10% -> WARNING
        - error_rate > 10% -> CRITICAL
        """
        if total_requests == 0:
            return "HEALTHY"
        if error_rate > 10.0:
            return "CRITICAL"
        if error_rate >= 5.0:
            return "WARNING"
        return "HEALTHY"


# Global singleton instance
redis_manager = RedisMetricsManager()
