"""数据模型：topic 诊断结果的结构化表示。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import IntEnum


class TopicStatus(IntEnum):
    OK = 0
    WARN = 1
    ERROR = 2


@dataclass
class QoSInfo:
    reliability: str = "UNKNOWN"
    durability: str = "UNKNOWN"
    deadline: str = "N/A"
    history: str = "UNKNOWN"
    depth: int = 0
    liveliness: str = "UNKNOWN"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SampleResult:
    message_count: int = 0
    duration_sec: float = 0.0
    rate_hz: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TopicDiagnosis:
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

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.name
        d["qos_pub"] = self.qos_pub.to_dict()
        d["qos_sub"] = self.qos_sub.to_dict()
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
