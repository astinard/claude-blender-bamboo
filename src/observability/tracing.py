"""OpenTelemetry tracing for Claude Fab Lab.

Provides distributed tracing for request flow visibility across services.
"""

import os
from functools import wraps
from typing import Optional, Callable, Any
from contextlib import contextmanager

# OpenTelemetry imports - optional
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.trace import Status, StatusCode
    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False
    trace = None

from src.utils import get_logger

logger = get_logger("observability.tracing")

# Global tracer
_tracer: Optional["trace.Tracer"] = None
_initialized = False

# Configuration
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "claude-fab-lab")
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
TRACE_ENABLED = os.getenv("TRACE_ENABLED", "false").lower() == "true"


def setup_tracing(
    service_name: Optional[str] = None,
    otlp_endpoint: Optional[str] = None,
    console_export: bool = False
) -> bool:
    """Initialize OpenTelemetry tracing.

    Args:
        service_name: Name of the service for traces
        otlp_endpoint: OTLP collector endpoint (e.g., "http://localhost:4317")
        console_export: Whether to also export to console (for debugging)

    Returns:
        True if tracing was initialized successfully
    """
    global _tracer, _initialized

    if not TRACING_AVAILABLE:
        logger.warning("OpenTelemetry not installed. Tracing disabled.")
        return False

    if not TRACE_ENABLED and not otlp_endpoint:
        logger.info("Tracing disabled (set TRACE_ENABLED=true to enable)")
        return False

    if _initialized:
        logger.debug("Tracing already initialized")
        return True

    try:
        service = service_name or SERVICE_NAME
        endpoint = otlp_endpoint or OTEL_ENDPOINT

        # Create resource with service info
        resource = Resource.create({
            "service.name": service,
            "service.version": os.getenv("APP_VERSION", "1.0.0"),
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
        })

        # Create tracer provider
        provider = TracerProvider(resource=resource)

        # Add exporters
        if endpoint:
            otlp_exporter = OTLPSpanExporter(endpoint=endpoint)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(f"OTLP trace exporter configured: {endpoint}")

        if console_export:
            console_exporter = ConsoleSpanExporter()
            provider.add_span_processor(BatchSpanProcessor(console_exporter))
            logger.info("Console trace exporter configured")

        # Set as global provider
        trace.set_tracer_provider(provider)

        # Get tracer
        _tracer = trace.get_tracer(service)
        _initialized = True

        logger.info(f"Tracing initialized for service: {service}")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize tracing: {e}")
        return False


def get_tracer() -> Optional["trace.Tracer"]:
    """Get the global tracer instance."""
    global _tracer
    if not _initialized:
        setup_tracing()
    return _tracer


def instrument_fastapi(app):
    """Instrument a FastAPI application with tracing.

    Args:
        app: FastAPI application instance
    """
    if not TRACING_AVAILABLE:
        logger.warning("Cannot instrument FastAPI: OpenTelemetry not installed")
        return

    if not _initialized:
        setup_tracing()

    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumented with tracing")
    except Exception as e:
        logger.error(f"Failed to instrument FastAPI: {e}")


@contextmanager
def trace_span(name: str, attributes: Optional[dict] = None):
    """Context manager for creating a trace span.

    Usage:
        with trace_span("my_operation", {"key": "value"}) as span:
            # do work
            span.set_attribute("result", "success")
    """
    tracer = get_tracer()

    if tracer is None:
        # No-op if tracing not available
        yield NoOpSpan()
        return

    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        try:
            yield span
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


def trace_async(
    name: Optional[str] = None,
    attributes: Optional[dict] = None
) -> Callable:
    """Decorator to trace an async function.

    Usage:
        @trace_async("fetch_printer_status")
        async def get_status(printer_id: str):
            ...

        @trace_async(attributes={"operation": "database"})
        async def query_jobs():
            ...
    """
    def decorator(func: Callable) -> Callable:
        span_name = name or func.__name__

        @wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()

            if tracer is None:
                return await func(*args, **kwargs)

            with tracer.start_as_current_span(span_name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                # Add function args as attributes (sanitized)
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)

                try:
                    result = await func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise

        return wrapper
    return decorator


def trace_sync(
    name: Optional[str] = None,
    attributes: Optional[dict] = None
) -> Callable:
    """Decorator to trace a synchronous function."""
    def decorator(func: Callable) -> Callable:
        span_name = name or func.__name__

        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()

            if tracer is None:
                return func(*args, **kwargs)

            with tracer.start_as_current_span(span_name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                span.set_attribute("function.name", func.__name__)

                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise

        return wrapper
    return decorator


class NoOpSpan:
    """No-op span for when tracing is disabled."""

    def set_attribute(self, key: str, value: Any):
        pass

    def set_status(self, status: Any):
        pass

    def record_exception(self, exception: Exception):
        pass

    def add_event(self, name: str, attributes: Optional[dict] = None):
        pass


def add_span_attributes(**kwargs):
    """Add attributes to the current span.

    Usage:
        add_span_attributes(user_id="123", printer_model="X1C")
    """
    if not TRACING_AVAILABLE:
        return

    span = trace.get_current_span()
    if span:
        for key, value in kwargs.items():
            span.set_attribute(key, value)


def record_exception(exception: Exception, attributes: Optional[dict] = None):
    """Record an exception in the current span."""
    if not TRACING_AVAILABLE:
        return

    span = trace.get_current_span()
    if span:
        span.record_exception(exception, attributes=attributes)
        span.set_status(Status(StatusCode.ERROR, str(exception)))
