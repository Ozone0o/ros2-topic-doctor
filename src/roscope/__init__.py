"""Roscope: ROS 2 observability and diagnostic toolkit.

The public package deliberately contains no unconditional ROS 2 imports.  This
keeps the diagnostic engine, reporters, and CI integrations usable on a laptop
or in a build container while the ROS-backed collectors are loaded only when a
command actually needs a running ROS graph.
"""

from .core.engine import DiagnosticEngine
from .core.models import (
    EndpointInfo,
    Finding,
    GraphSnapshot,
    QoSInfo,
    SampleResult,
    ScanReport,
    TopicDiagnosis,
    TopicSnapshot,
    TopicStatus,
)
from .core.service import RoscopeService

__all__ = [
    "DiagnosticEngine",
    "EndpointInfo",
    "Finding",
    "GraphSnapshot",
    "QoSInfo",
    "SampleResult",
    "ScanReport",
    "TopicDiagnosis",
    "TopicSnapshot",
    "TopicStatus",
    "RoscopeService",
]

__version__ = "0.2.0"
