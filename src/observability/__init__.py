"""Observability module for Claude Fab Lab.

Provides structured logging, Prometheus metrics, and OpenTelemetry tracing.
"""

from src.observability.logging import (
    setup_logging,
    get_logger,
    LogContext,
)
from src.observability.metrics import (
    setup_metrics,
    get_metrics,
    MetricsMiddleware,
    # Counters
    http_requests_total,
    print_jobs_total,
    ai_generations_total,
    mqtt_messages_total,
    # Histograms
    http_request_duration,
    print_job_duration,
    mqtt_latency,
    # Gauges
    active_printers,
    active_jobs,
    queue_size,
)
from src.observability.tracing import (
    setup_tracing,
    get_tracer,
    trace_async,
)

__all__ = [
    # Logging
    "setup_logging",
    "get_logger",
    "LogContext",
    # Metrics
    "setup_metrics",
    "get_metrics",
    "MetricsMiddleware",
    "http_requests_total",
    "print_jobs_total",
    "ai_generations_total",
    "mqtt_messages_total",
    "http_request_duration",
    "print_job_duration",
    "mqtt_latency",
    "active_printers",
    "active_jobs",
    "queue_size",
    # Tracing
    "setup_tracing",
    "get_tracer",
    "trace_async",
]
