"""OpenTelemetry setup — traces and metrics."""
import logging
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger(__name__)

_tracer = None
_meter = None


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
    if _meter is None:
        return
    try:
        hist = _meter.create_histogram("llm.latency_ms", unit="ms")
        hist.record(ms, {"model": model, "agent_type": agent_type})
    except Exception:
        pass


def record_agent_task(agent_type: str, status: str):
    if _meter is None:
        return
    try:
        counter = _meter.create_counter("agent.tasks_total")
        counter.add(1, {"agent_type": agent_type, "status": status})
    except Exception:
        pass
