"""Prometheus metrics for Claude Fab Lab.

Provides application metrics for monitoring and alerting.
"""

import time
from typing import Callable, Optional
from functools import wraps

try:
    from prometheus_client import (
        Counter, Histogram, Gauge, Summary,
        generate_latest, CONTENT_TYPE_LATEST,
        CollectorRegistry, REGISTRY,
        multiprocess, CollectorRegistry
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Create dummy classes for when prometheus_client is not installed
    class DummyMetric:
        def labels(self, **kwargs): return self
        def inc(self, amount=1): pass
        def dec(self, amount=1): pass
        def set(self, value): pass
        def observe(self, amount): pass
        def time(self): return DummyTimer()

    class DummyTimer:
        def __enter__(self): return self
        def __exit__(self, *args): pass

    Counter = Histogram = Gauge = Summary = lambda *args, **kwargs: DummyMetric()

from src.observability.logging import get_logger

logger = get_logger("observability.metrics")


# ============================================================================
# HTTP Metrics
# ============================================================================

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

http_request_duration = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently being processed",
    ["method", "endpoint"]
)


# ============================================================================
# Print Job Metrics
# ============================================================================

print_jobs_total = Counter(
    "print_jobs_total",
    "Total print jobs",
    ["status", "material", "printer_model"]
)

print_job_duration = Histogram(
    "print_job_duration_minutes",
    "Print job duration in minutes",
    ["material", "printer_model"],
    buckets=[5, 15, 30, 60, 120, 240, 480, 960, 1440]  # Up to 24 hours
)

print_material_usage = Counter(
    "print_material_usage_grams_total",
    "Total material used in grams",
    ["material_type", "color"]
)

active_jobs = Gauge(
    "active_jobs",
    "Currently active print jobs"
)

queue_size = Gauge(
    "queue_size",
    "Number of jobs in queue",
    ["priority"]
)


# ============================================================================
# Printer Metrics
# ============================================================================

active_printers = Gauge(
    "active_printers",
    "Number of connected printers",
    ["model"]
)

printer_temperature = Gauge(
    "printer_temperature_celsius",
    "Printer temperature readings",
    ["printer_id", "component"]  # component: bed, nozzle, chamber
)

printer_errors_total = Counter(
    "printer_errors_total",
    "Total printer errors",
    ["printer_id", "error_type"]
)


# ============================================================================
# AI Generation Metrics
# ============================================================================

ai_generations_total = Counter(
    "ai_generations_total",
    "Total AI model generations",
    ["provider", "status"]
)

ai_generation_duration = Histogram(
    "ai_generation_duration_seconds",
    "AI generation duration in seconds",
    ["provider"],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600]
)


# ============================================================================
# MQTT Metrics
# ============================================================================

mqtt_messages_total = Counter(
    "mqtt_messages_total",
    "Total MQTT messages",
    ["direction", "printer_id"]  # direction: sent, received
)

mqtt_latency = Histogram(
    "mqtt_latency_milliseconds",
    "MQTT message round-trip latency",
    ["printer_id"],
    buckets=[10, 25, 50, 100, 250, 500, 1000, 2500]
)

mqtt_connection_status = Gauge(
    "mqtt_connection_status",
    "MQTT connection status (1=connected, 0=disconnected)",
    ["printer_id"]
)


# ============================================================================
# Database Metrics
# ============================================================================

db_connections_active = Gauge(
    "db_connections_active",
    "Active database connections"
)

db_query_duration = Histogram(
    "db_query_duration_seconds",
    "Database query duration",
    ["operation"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)


# ============================================================================
# Utility Functions
# ============================================================================

def setup_metrics():
    """Initialize metrics (placeholder for multiprocess mode setup)."""
    if not PROMETHEUS_AVAILABLE:
        logger.warning("prometheus_client not installed, metrics disabled")
        return
    logger.info("Metrics initialized")


def get_metrics() -> bytes:
    """Generate Prometheus metrics output."""
    if not PROMETHEUS_AVAILABLE:
        return b"# Prometheus client not available\n"
    return generate_latest(REGISTRY)


def get_metrics_content_type() -> str:
    """Get content type for metrics endpoint."""
    if not PROMETHEUS_AVAILABLE:
        return "text/plain"
    return CONTENT_TYPE_LATEST


class MetricsMiddleware:
    """FastAPI middleware for HTTP metrics."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        path = scope["path"]

        # Skip metrics endpoint
        if path == "/metrics":
            await self.app(scope, receive, send)
            return

        # Normalize path (remove IDs)
        endpoint = self._normalize_path(path)

        start_time = time.time()
        http_requests_in_progress.labels(method=method, endpoint=endpoint).inc()

        status_code = 500
        try:
            async def send_wrapper(message):
                nonlocal status_code
                if message["type"] == "http.response.start":
                    status_code = message["status"]
                await send(message)

            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.time() - start_time
            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status=status_code
            ).inc()
            http_request_duration.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
            http_requests_in_progress.labels(method=method, endpoint=endpoint).dec()

    def _normalize_path(self, path: str) -> str:
        """Normalize path by replacing IDs with placeholders."""
        import re
        # Replace UUIDs
        path = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "{id}",
            path
        )
        # Replace numeric IDs
        path = re.sub(r"/\d+(/|$)", "/{id}\\1", path)
        return path


def timed_operation(metric: Histogram, **labels):
    """Decorator to time operations."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with metric.labels(**labels).time():
                return func(*args, **kwargs)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                metric.labels(**labels).observe(time.time() - start)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper
    return decorator
