"""LangSmith tracing via OpenTelemetry + OpenInference instrumentation.

Initialises OTel TracerProvider with LangSmith's OtelSpanProcessor,
then instruments both CrewAI and OpenAI so every agent action and
LLM call is traced and visible in the LangSmith dashboard.

Call ``init_tracing()`` once at application startup.
"""

from __future__ import annotations

import os
import structlog

logger = structlog.get_logger(__name__)


def init_tracing() -> bool:
    """Set up LangSmith tracing. Returns True if successful."""

    # Only proceed if tracing is explicitly enabled
    if os.environ.get("LANGSMITH_TRACING", "").lower() != "true":
        logger.info("langsmith_tracing_disabled")
        return False

    api_key = os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")
    if not api_key:
        logger.warning("langsmith_tracing_no_api_key")
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from langsmith.integrations.otel import OtelSpanProcessor
        from openinference.instrumentation.crewai import CrewAIInstrumentor
        from openinference.instrumentation.openai import OpenAIInstrumentor

        # Configure OpenTelemetry TracerProvider
        tracer_provider = trace.get_tracer_provider()
        if not isinstance(tracer_provider, TracerProvider):
            tracer_provider = TracerProvider()
            trace.set_tracer_provider(tracer_provider)

        # Add LangSmith span processor
        tracer_provider.add_span_processor(OtelSpanProcessor())

        # Instrument CrewAI and OpenAI
        CrewAIInstrumentor().instrument()
        OpenAIInstrumentor().instrument()

        project = os.environ.get("LANGSMITH_PROJECT") or os.environ.get("LANGCHAIN_PROJECT", "default")
        logger.info(
            "langsmith_tracing_initialised",
            project=project,
            endpoint=os.environ.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"),
        )
        return True

    except ImportError as exc:
        logger.warning("langsmith_tracing_import_error", missing=str(exc))
        return False
    except Exception as exc:
        logger.error("langsmith_tracing_init_error", error=str(exc))
        return False
