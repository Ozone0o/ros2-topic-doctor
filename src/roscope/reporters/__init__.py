"""Output adapters for terminals, automation, and documentation."""

from .json import (
    format_diagnosis_json,
    format_graph_json,
    format_scan_json,
)
from .markdown import format_markdown_report
from .terminal import format_diagnosis_text, format_graph_text, format_scan_text

__all__ = [
    "format_diagnosis_json",
    "format_graph_json",
    "format_scan_json",
    "format_markdown_report",
    "format_diagnosis_text",
    "format_graph_text",
    "format_scan_text",
]
