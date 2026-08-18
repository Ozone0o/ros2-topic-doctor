"""Tests for the canonical Roscope diagnostic engine."""

from __future__ import annotations

from roscope.core.engine import DiagnosticEngine
from roscope.core.models import TopicDiagnosis, TopicStatus


def analyze(diagnosis: TopicDiagnosis, **kwargs) -> TopicDiagnosis:
    return DiagnosticEngine().analyze(diagnosis, **kwargs)


def test_topic_not_found() -> None:
    result = analyze(TopicDiagnosis(topic_name="/fake/topic"))
    assert result.status == TopicStatus.ERROR
    assert result.findings[0].code == "topic_missing"


def test_publisher_without_messages() -> None:
    result = analyze(
        TopicDiagnosis(topic_name="/camera", pub_count=1, sub_count=1, sample_duration_sec=1.0)
    )
    assert result.status == TopicStatus.ERROR
    assert result.findings[0].code == "publisher_no_messages"


def test_stale_message() -> None:
    result = analyze(
        TopicDiagnosis(
            topic_name="/scan",
            pub_count=1,
            sub_count=1,
            rate=10.0,
            last_message_age_ms=10000.0,
            last_message_seen=True,
        ),
        stale_timeout_ms=5000.0,
    )
    assert result.status == TopicStatus.ERROR
    assert any(finding.code == "stale_messages" for finding in result.findings)


def test_rate_and_subscriber_warnings() -> None:
    result = analyze(
        TopicDiagnosis(topic_name="/scan", pub_count=1, rate=5.0),
        expected_rate=30.0,
    )
    assert result.status == TopicStatus.WARN
    assert {finding.code for finding in result.findings} >= {
        "frequency_degraded",
        "no_subscribers",
    }


def test_qos_warning() -> None:
    result = analyze(
        TopicDiagnosis(
            topic_name="/scan",
            pub_count=1,
            sub_count=1,
            rate=10.0,
            qos_profile_missing=["QoS profiles differ"],
        )
    )
    assert result.status == TopicStatus.WARN
    assert any(finding.code == "qos_mismatch" for finding in result.findings)


def test_healthy_topic() -> None:
    result = analyze(
        TopicDiagnosis(
            topic_name="/joint_states",
            pub_count=1,
            sub_count=2,
            rate=50.0,
            last_message_age_ms=10.0,
            last_message_seen=True,
        ),
        expected_rate=50.0,
    )
    assert result.status == TopicStatus.OK
    assert not result.findings
