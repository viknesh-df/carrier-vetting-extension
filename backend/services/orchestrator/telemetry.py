"""
OpenTelemetry setup for the orchestrator service
"""
import os
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

def setup_telemetry():
    """Setup OpenTelemetry for the orchestrator service"""
    
    # Get configuration from environment
    otel_endpoint = os.getenv("OTEL_ENDPOINT", "http://monitoring:4317")
    enable_console_export = os.getenv("OTEL_CONSOLE_EXPORT", "true").lower() == "true"
    
    # Setup trace provider
    trace_provider = TracerProvider()
    
    # Add span processors
    if enable_console_export:
        trace_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    
    # Set the trace provider
    trace.set_tracer_provider(trace_provider)
    
    # Setup metrics provider
    metric_reader = PeriodicExportingMetricReader(ConsoleMetricExporter())
    metric_provider = MeterProvider(metric_readers=[metric_reader])
    metrics.set_meter_provider(metric_provider)
    
    # Instrument HTTPX client
    HTTPXClientInstrumentor().instrument()
    
    print(f"OpenTelemetry setup complete. Endpoint: {otel_endpoint}")

def instrument_fastapi(app):
    """Instrument FastAPI application with OpenTelemetry"""
    FastAPIInstrumentor.instrument_app(app)
    print("FastAPI instrumented with OpenTelemetry")
