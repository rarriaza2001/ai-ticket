"""OpenTelemetry and metrics hooks (disabled in Phase 1)."""


def configure_tracing(*, enabled: bool = False) -> None:
    """Wire OTLP exporters and auto-instrumentation in Phase 2."""
    if enabled:
        raise NotImplementedError("Tracing is not configured in Phase 1.")
