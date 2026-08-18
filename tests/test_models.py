"""Tests for Roscope's stable diagnostic models."""

from __future__ import annotations

import json

from roscope.core.models import QoSInfo, SampleResult, TopicDiagnosis, TopicStatus


def test_qos_defaults_and_serialization() -> None:
    qos = QoSInfo()
    assert qos.reliability == "UNKNOWN"
    assert qos.depth == 0
    assert QoSInfo(reliability="RELIABLE", depth=10).to_dict()["depth"] == 10


def test_sample_result_serialization() -> None:
    sample = SampleResult(message_count=30, duration_sec=1.0, rate_hz=30.0)
    assert sample.to_dict()["message_count"] == 30


def test_topic_diagnosis_json_contract() -> None:
    diagnosis = TopicDiagnosis(topic_name="/scan", pub_count=1, sub_count=2, rate=10.0)
    data = json.loads(diagnosis.to_json(indent=None))
    assert data["topic_name"] == "/scan"
    assert data["status"] == "OK"


def test_topic_diagnosis_exit_code_follows_status() -> None:
    diagnosis = TopicDiagnosis(topic_name="/scan", status=TopicStatus.WARN)
    assert diagnosis.exit_code == 1
