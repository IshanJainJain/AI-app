"""OpenTelemetry setup — traces and metrics."""
import logging
import threading
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger(__name__)

_tracer = None
_meter = None
_kb_degraded_count: int = 0
_kb_degraded_lock = threading.Lock()
_llm_latency_hist = None
_agent_tasks_counter = None


def _observe_kb_degraded_gauge(options):
    """Module-level callback so the binding to _kb_degraded_count is unambiguous."""
    from opentelemetry.metrics import Observation
    with _kb_degraded_lock:
        count = _kb_degraded_count
    yield Observation(count)


def setup_telemetry(service_name: str, service_version: str, otlp_endpoint: str):
    global _tracer, _meter
    try:
        from opentelemetry import trace, metrics
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({
            "service.name": service_name,
            "service.version": service_version,
        })

        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True))
        )
        trace.set_tracer_provider(tracer_provider)
        _tracer = trace.get_tracer(service_name, service_version)

        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[
                PeriodicExportingMetricReader(
                    OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True)
                )
            ],
        )
        metrics.set_meter_provider(meter_provider)
        _meter = metrics.get_meter(service_name, service_version)

        global _llm_latency_hist, _agent_tasks_counter
        _llm_latency_hist = _meter.create_histogram("llm.latency_ms", unit="ms")
        _agent_tasks_counter = _meter.create_counter("agent.tasks_total")

        _meter.create_observable_gauge(
            "kb_degraded_documents_total",
            callbacks=[_observe_kb_degraded_gauge],
            description="KB documents stored in FAISS fallback instead of Qdrant",
        )

        logger.info("OpenTelemetry configured → %s", otlp_endpoint)
    except Exception as exc:
        logger.warning("OTEL setup failed (continuing without telemetry): %s", exc)


def instrument_fastapi(app):
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except Exception as exc:
        logger.warning("FastAPI OTEL instrumentation failed: %s", exc)


@contextmanager
def trace_span(name: str, attributes: dict = None) -> Generator:
    if _tracer is None:
        yield None
        return
    with _tracer.start_as_current_span(name) as span:
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, str(v))
        yield span


def get_current_trace_id() -> str:
    try:
        from opentelemetry import trace
        ctx = trace.get_current_span().get_span_context()
        return format(ctx.trace_id, "032x") if ctx.is_valid else ""
    except Exception:
        return ""


def record_llm_latency(ms: int, model: str, agent_type: str):
    if _llm_latency_hist is None:
        return
    try:
        _llm_latency_hist.record(ms, {"model": model, "agent_type": agent_type})
    except Exception:
        pass


def record_agent_task(agent_type: str, status: str):
    if _agent_tasks_counter is None:
        return
    try:
        _agent_tasks_counter.add(1, {"agent_type": agent_type, "status": status})
    except Exception:
        pass


def record_rag_event(event_name: str, **attributes):
    """Add a named event to the current span (falls back to a log line when no active span)."""
    log_attrs = " ".join(f"{k}={v}" for k, v in attributes.items())
    logger.info("rag_event %s %s", event_name, log_attrs)
    if _tracer is None:
        return
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        if span.is_recording():
            span.add_event(event_name, {k: str(v) for k, v in attributes.items()})
    except Exception:
        pass


def set_kb_degraded_count(n: int):
    """Update the in-process snapshot used by the kb_degraded_documents_total gauge."""
    global _kb_degraded_count
    with _kb_degraded_lock:
        _kb_degraded_count = n
