"""
OpenTelemetry Tracing & Observability for ADK 2.0.

Instruments ADK model calls, tool executions, and graph workflows using `google.adk.telemetry`.
Supports optional OTLP exporter export to Jaeger, Zipkin, or GCP Cloud Trace.
"""

import logging
import os
import typing

from google.adk.telemetry import TelemetryConfig

logger = logging.getLogger(__name__)

_TELEMETRY_INITIALIZED = False

def setup_telemetry(app_name: str = "personal-assistant-adk") -> dict[str, typing.Any]:
    """
    Initialize OpenTelemetry tracing for ADK.
    Reads OTEL_EXPORTER_OTLP_ENDPOINT from environment if provided.
    """
    global _TELEMETRY_INITIALIZED

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    capture_content = os.getenv("TELEMETRY_CAPTURE_CONTENT", "true").lower() in ("true", "1")

    # Initialize TelemetryConfig
    TelemetryConfig(
        capture_message_content=capture_content,
        genai_semconv_stability_opt_in=True,
    )

    _TELEMETRY_INITIALIZED = True
    logger.info("ADK OpenTelemetry tracing configured (app=%s, otlp_endpoint=%s)", app_name, otlp_endpoint or "none")

    return {
        "status": "active",
        "app_name": app_name,
        "otlp_endpoint": otlp_endpoint or "none",
        "capture_content": capture_content,
    }

def get_telemetry_status() -> dict[str, typing.Any]:
    """Return OpenTelemetry instrumentation status."""
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    return {
        "initialized": _TELEMETRY_INITIALIZED,
        "provider": "google.adk.telemetry",
        "otlp_endpoint": otlp_endpoint or "none",
        "capture_content": os.getenv("TELEMETRY_CAPTURE_CONTENT", "true").lower() in ("true", "1"),
    }
