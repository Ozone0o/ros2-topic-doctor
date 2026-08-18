"""Topic-level analysis entry point for built-in and plugin callers."""

from __future__ import annotations

from roscope.core.engine import DiagnosticEngine
from roscope.core.models import TopicDiagnosis


def analyze_topic(
    diagnosis: TopicDiagnosis,
    *,
    expected_rate: float = 0.0,
    stale_timeout_ms: float = 5000.0,
    engine: DiagnosticEngine | None = None,
) -> TopicDiagnosis:
    """Analyze one topic using the default or supplied diagnostic engine."""

    return (engine or DiagnosticEngine()).analyze(
        diagnosis,
        expected_rate=expected_rate,
        stale_timeout_ms=stale_timeout_ms,
    )
