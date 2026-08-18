"""Stable, JSON-serialisable domain models used by every Roscope layer."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class TopicStatus(IntEnum):
    """Health status and default process exit code for a diagnostic result."""

    OK = 0
    WARN = 1
    ERROR = 2

    @property
    def label(self) -> str:
        return self.name


def _enum_name(value: Any, default: str = "UNKNOWN") -> str:
    """Return a useful name for ROS enum values and ordinary strings."""

    if value is None:
        return default
    name = getattr(value, "name", None)
    if name:
        return str(name)
    text = str(value)
    return text if text else default


@dataclass
class QoSInfo:
    """The subset of a ROS 2 QoS profile useful during diagnosis."""

    reliability: str = "UNKNOWN"
    durability: str = "UNKNOWN"
    deadline: str = "N/A"
    history: str = "UNKNOWN"
    depth: int = 0
    liveliness: str = "UNKNOWN"

    def to_dict(self) -> dict[str, Any]:
        return {
            "reliability": _enum_name(self.reliability),
            "durability": _enum_name(self.durability),
            "deadline": str(self.deadline),
            "history": _enum_name(self.history),
            "depth": self.depth,
            "liveliness": _enum_name(self.liveliness),
        }


@dataclass
class EndpointInfo:
    """A publisher or subscription discovered in the ROS graph."""

    node_name: str = ""
    node_namespace: str = ""
    topic_type: str = "N/A"
    qos: QoSInfo = field(default_factory=QoSInfo)

    @property
    def fully_qualified_node(self) -> str:
        namespace = self.node_namespace.rstrip("/")
        return f"{namespace}/{self.node_name}" if namespace else self.node_name

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_name": self.node_name,
            "node_namespace": self.node_namespace,
            "node": self.fully_qualified_node,
            "topic_type": self.topic_type,
            "qos": self.qos.to_dict(),
        }


@dataclass
class Finding:
    """An actionable explanation produced by the diagnostic engine."""

    code: str
    severity: TopicStatus
    problem: str
    detail: str = ""
    possible_causes: list[str] = field(default_factory=list)
    suggested_commands: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "status": self.severity.name,
            "severity": self.severity.name,
            "problem": self.problem,
            "detail": self.detail,
            "possible_causes": list(self.possible_causes),
            "suggested_commands": list(self.suggested_commands),
            "evidence": self.evidence,
        }


@dataclass
class SampleResult:
    """Measurements collected during one observation window."""

    message_count: int = 0
    duration_sec: float = 0.0
    rate_hz: float = 0.0
    last_message_age_ms: float = 0.0
    received: bool = False
    qos_source: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_count": self.message_count,
            "duration_sec": self.duration_sec,
            "rate_hz": self.rate_hz,
            "last_message_age_ms": self.last_message_age_ms,
            "received": self.received,
            "qos_source": self.qos_source,
        }


@dataclass
class TopicSnapshot:
    """Metadata collected from the ROS graph before analysis."""

    topic_name: str
    msg_type: str = "N/A"
    topic_exists: bool = False
    publishers: list[EndpointInfo] = field(default_factory=list)
    subscribers: list[EndpointInfo] = field(default_factory=list)
    qos_issues: list[str] = field(default_factory=list)

    @property
    def pub_count(self) -> int:
        return len(self.publishers)

    @property
    def sub_count(self) -> int:
        return len(self.subscribers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic_name": self.topic_name,
            "msg_type": self.msg_type,
            "topic_exists": self.topic_exists,
            "pub_count": self.pub_count,
            "sub_count": self.sub_count,
            "publishers": [endpoint.to_dict() for endpoint in self.publishers],
            "subscribers": [endpoint.to_dict() for endpoint in self.subscribers],
            "qos_issues": list(self.qos_issues),
        }


@dataclass
class TopicDiagnosis:
    """Complete diagnosis for one topic.

    The flat fields are intentionally stable for CI and integration scripts;
    ``findings`` and ``to_dict()`` provide the richer canonical contract.
    """

    topic_name: str = ""
    msg_type: str = "N/A"
    pub_count: int = 0
    sub_count: int = 0
    rate: float = 0.0
    expected_rate: float = 0.0
    last_message_age_ms: float = 0.0
    qos_pub: QoSInfo = field(default_factory=QoSInfo)
    qos_sub: QoSInfo = field(default_factory=QoSInfo)
    qos_profile_missing: list[str] = field(default_factory=list)
    status: TopicStatus = TopicStatus.OK
    notes: list[str] = field(default_factory=list)
    stale_timeout_ms: float = 0.0
    topic_exists: bool | None = None
    message_count: int = 0
    sample_duration_sec: float = 0.0
    last_message_seen: bool = False
    publishers: list[EndpointInfo] = field(default_factory=list)
    subscribers: list[EndpointInfo] = field(default_factory=list)
    qos_issues: list[str] = field(default_factory=list)
    collection_errors: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    observation_qos: str = "unknown"

    @property
    def exit_code(self) -> int:
        return int(self.status)

    @property
    def healthy(self) -> bool:
        return self.status == TopicStatus.OK

    @property
    def possible_causes(self) -> list[str]:
        return _unique(cause for finding in self.findings for cause in finding.possible_causes)

    @property
    def suggested_commands(self) -> list[str]:
        return _unique(
            command for finding in self.findings for command in finding.suggested_commands
        )

    def add_finding(self, finding: Finding) -> None:
        self.findings.append(finding)
        if finding.severity > self.status:
            self.status = finding.severity

    def to_dict(self) -> dict[str, Any]:
        """Return the stable flat JSON document plus structured findings.

        Stable field names are preferable for CI.  New nested fields are
        additive, so a script that only reads ``status`` or ``rate`` keeps
        working after upgrading.
        """

        return {
            "schema_version": "1.0",
            "topic_name": self.topic_name,
            "msg_type": self.msg_type,
            "topic_exists": self.topic_exists,
            "pub_count": self.pub_count,
            "sub_count": self.sub_count,
            "rate": self.rate,
            "expected_rate": self.expected_rate,
            "last_message_age_ms": self.last_message_age_ms,
            "message_count": self.message_count,
            "sample_duration_sec": self.sample_duration_sec,
            "last_message_seen": self.last_message_seen,
            "stale_timeout_ms": self.stale_timeout_ms,
            "qos_pub": self.qos_pub.to_dict(),
            "qos_sub": self.qos_sub.to_dict(),
            "qos_profile_missing": list(self.qos_profile_missing),
            "qos_issues": list(self.qos_issues),
            "publishers": [endpoint.to_dict() for endpoint in self.publishers],
            "subscribers": [endpoint.to_dict() for endpoint in self.subscribers],
            "status": self.status.name,
            "exit_code": self.exit_code,
            "notes": list(self.notes),
            "collection_errors": list(self.collection_errors),
            "findings": [finding.to_dict() for finding in self.findings],
            "observation_qos": self.observation_qos,
            "possible_causes": self.possible_causes,
            "suggested_commands": self.suggested_commands,
        }

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


@dataclass
class ScanReport:
    """A fleet-level result returned by ``roscope scan`` and ``report``."""

    topics: list[TopicDiagnosis] = field(default_factory=list)
    duration_sec: float = 0.0

    @property
    def status(self) -> TopicStatus:
        if not self.topics:
            return TopicStatus.OK
        return max((topic.status for topic in self.topics), default=TopicStatus.OK)

    @property
    def exit_code(self) -> int:
        return int(self.status)

    @property
    def summary(self) -> dict[str, int]:
        return {
            "topics": len(self.topics),
            "ok": sum(topic.status == TopicStatus.OK for topic in self.topics),
            "warn": sum(topic.status == TopicStatus.WARN for topic in self.topics),
            "error": sum(topic.status == TopicStatus.ERROR for topic in self.topics),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "status": self.status.name,
            "exit_code": self.exit_code,
            "duration_sec": self.duration_sec,
            "summary": self.summary,
            "topics": [topic.to_dict() for topic in self.topics],
        }


@dataclass
class GraphSnapshot:
    """ROS graph metadata used by the graph reporter."""

    nodes: list[dict[str, Any]] = field(default_factory=list)
    topics: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "nodes": list(self.nodes),
            "topics": list(self.topics),
            "summary": {
                "nodes": len(self.nodes),
                "topics": len(self.topics),
            },
        }


def _unique(values: Any) -> list[str]:
    """Deduplicate strings while preserving discovery order."""

    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def qos_info_from_profile(profile: Any) -> QoSInfo:
    """Convert a rclpy QoS profile without importing rclpy."""

    if profile is None:
        return QoSInfo()
    return QoSInfo(
        reliability=_enum_name(getattr(profile, "reliability", None)),
        durability=_enum_name(getattr(profile, "durability", None)),
        deadline=str(getattr(profile, "deadline", "N/A")),
        history=_enum_name(getattr(profile, "history", None)),
        depth=int(getattr(profile, "depth", 0) or 0),
        liveliness=_enum_name(getattr(profile, "liveliness", None)),
    )
