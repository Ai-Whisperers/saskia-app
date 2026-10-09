"""app/rms/otel.py — OpenTelemetry + Prometheus instrumentation.

Why this module exists:
    The Sazon app currently has Sentry for error tracking (in
    app/rms/notify.py + lifespan in app/rms/main.py) but NO distributed
    tracing or metrics. Debugging prod issues requires log-speleology.

    This module adds:
        - OpenTelemetry tracing (FastAPI + SQLAlchemy auto-instrumentation)
        - Prometheus metrics endpoint at /metrics
        - OTLP exporter (configurable endpoint; no-op if unset)

Activation:
    Set OTEL_ENABLED=true and (optionally) OTEL_EXPORTER_OTLP_ENDPOINT.
    The app lifespan picks this up automatically — no code change.

    Set PROMETHEUS_ENABLED=true to expose /metrics.
    By default, /metrics is NOT exposed (operator chooses).

Why env-gated, not always-on:
    - Sazon is a one-bakery app; the operator may not want the OTel
      overhead on every request
    - The OTel SDK is a transitive dep; bundling it always-on forces
      the dev install to grow ~6 MB
    - Tests don't need real OTel; mock instrumentation is fine

References:
    https://fastapi.tiangolo.com/advanced/opentelemetry/
    docs/operations/2026-10-09-tooling-research.md
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI


def _truthy(value: str | None) -> bool:
    """Return True if the env var is set to a truthy value."""
    if not value:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def init_observability(app: "FastAPI") -> None:
    """Wire up OTel + Prometheus. Idempotent; safe to call from lifespan.

    Behavior matrix:

    | OTEL_ENABLED | OTEL_EXPORTER_OTLP_ENDPOINT | Effect           |
    |--------------|------------------------------|------------------|
    | unset/0      | (any)                        | no-op            |
    | 1/true       | unset                        | no-op (warn)     |
    | 1/true       | set                          | init + exporter  |

    | PROMETHEUS_ENABLED | Effect                       |
    |--------------------|------------------------------|
    | unset/0            | /metrics NOT exposed         |
    | 1/true             | /metrics exposed at /metrics |
    """
    if _truthy(os.getenv("OTEL_ENABLED")):
        _init_opentelemetry(app)
    else:
        print("[otel] OTel not enabled (set OTEL_ENABLED=true to enable)", file=sys.stderr)

    if _truthy(os.getenv("PROMETHEUS_ENABLED")):
        _init_prometheus(app)
    else:
        print(
            "[otel] Prometheus not enabled (set PROMETHEUS_ENABLED=true to enable)", file=sys.stderr
        )


def _init_opentelemetry(app: "FastAPI") -> None:
    """Initialize OpenTelemetry tracing. No-op if endpoint unset."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        print(
            "WARNING: OTEL_ENABLED=true but OTEL_EXPORTER_OTLP_ENDPOINT is unset. "
            "Traces will be created but not exported. Set OTEL_EXPORTER_OTLP_ENDPOINT "
            "to your OTel collector (e.g. http://localhost:4317).",
            file=sys.stderr,
        )
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        service_name = os.getenv("OTEL_SERVICE_NAME", "sazon-rms")
        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)

        # Auto-instrument FastAPI (HTTP spans) + SQLAlchemy (DB spans)
        FastAPIInstrumentor.instrument_app(app)
        try:
            from app.rms.db import engine

            SQLAlchemyInstrumentor().instrument(engine=engine)
        except Exception as exc:  # pragma: no cover — engine may not be ready
            print(f"WARNING: SQLAlchemy OTel instrumentation skipped: {exc}", file=sys.stderr)

        print(f"OTel tracing enabled → {endpoint} (service={service_name})")
    except ImportError as exc:
        print(
            f"WARNING: OTel enabled but imports failed: {exc}. "
            f"Install with: uv sync --group tooling-tier2",
            file=sys.stderr,
        )


def _init_prometheus(app: "FastAPI") -> None:
    """Expose Prometheus metrics at /metrics. Off by default."""
    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator(
            should_group_status_codes=False,
            should_ignore_untemplated=True,
            should_group_untemplated=True,
        ).instrument(app).expose(
            app,
            endpoint="/metrics",
            include_in_schema=False,  # don't expose in OpenAPI docs
        )
        print("Prometheus /metrics endpoint enabled (set PROMETHEUS_ENABLED=true)")
    except ImportError as exc:
        print(
            f"WARNING: Prometheus enabled but imports failed: {exc}. "
            f"Install with: uv sync --group tooling-tier2",
            file=sys.stderr,
        )
