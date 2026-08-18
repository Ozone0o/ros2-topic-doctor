"""Machine-readable JSON reporters.

The schema is intentionally boring: one object per command and one stable
``status``/``exit_code`` pair.  ``watch --json`` uses JSON Lines so it can be
consumed incrementally by a log processor.
"""

from __future__ import annotations

import json
from typing import Any

from roscope.core.models import GraphSnapshot, ScanReport, TopicDiagnosis


def _dump(payload: dict[str, Any], *, indent: int | None = 2) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=indent, sort_keys=False)


def format_diagnosis_json(diagnosis: TopicDiagnosis, *, indent: int | None = 2) -> str:
    return _dump(diagnosis.to_dict(), indent=indent)


def format_scan_json(report: ScanReport, *, indent: int | None = 2) -> str:
    return _dump(report.to_dict(), indent=indent)


def format_graph_json(graph: GraphSnapshot, *, indent: int | None = 2) -> str:
    return _dump(graph.to_dict(), indent=indent)


def format_json_line(value: Any) -> str:
    """Serialize a watch event without pretty-print whitespace."""

    if hasattr(value, "to_dict"):
        value = value.to_dict()
    return _dump(value, indent=None)
