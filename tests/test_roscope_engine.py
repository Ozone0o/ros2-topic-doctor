"""Deterministic tests for Roscope's explanation engine."""

import json

from roscope.core.engine import DiagnosticEngine
from roscope.core.models import EndpointInfo, QoSInfo, TopicDiagnosis, TopicStatus


def test_missing_topic_has_actionable_finding() -> None:
    result = DiagnosticEngine().analyze(
        TopicDiagnosis(topic_name="/missing", topic_exists=False),
    )

    assert result.status == TopicStatus.ERROR
    assert result.findings[0].code == "topic_missing"
    assert "roscope graph" in result.suggested_commands
    assert result.possible_causes


def test_publisher_without_messages_is_error() -> None:
    result = DiagnosticEngine().analyze(
        TopicDiagnosis(
            topic_name="/camera/image_raw",
            topic_exists=True,
            pub_count=1,
            sub_count=2,
            sample_duration_sec=3.0,
            message_count=0,
        )
    )

    assert result.status == TopicStatus.ERROR
    assert any(finding.code == "publisher_no_messages" for finding in result.findings)
    assert any("driver" in cause for cause in result.possible_causes)


def test_frequency_degradation_is_warning() -> None:
    result = DiagnosticEngine().analyze(
        TopicDiagnosis(
            topic_name="/scan",
            topic_exists=True,
            pub_count=1,
            sub_count=1,
            rate=5.0,
            message_count=15,
            sample_duration_sec=3.0,
        ),
        expected_rate=10.0,
    )

    assert result.status == TopicStatus.WARN
    assert result.findings[0].code == "frequency_degraded"


def test_qos_incompatibility_is_error() -> None:
    publisher = EndpointInfo(
        node_name="camera",
        topic_type="sensor_msgs/msg/Image",
        qos=QoSInfo(reliability="BEST_EFFORT"),
    )
    subscriber = EndpointInfo(
        node_name="perception",
        topic_type="sensor_msgs/msg/Image",
        qos=QoSInfo(reliability="RELIABLE"),
    )
    result = DiagnosticEngine().analyze(
        TopicDiagnosis(
            topic_name="/camera/image_raw",
            topic_exists=True,
            pub_count=1,
            sub_count=1,
            publishers=[publisher],
            subscribers=[subscriber],
            qos_issues=["Incompatible reliability: BEST_EFFORT vs RELIABLE"],
            rate=30.0,
            message_count=30,
            sample_duration_sec=1.0,
            last_message_seen=True,
            last_message_age_ms=10.0,
        )
    )

    assert result.status == TopicStatus.ERROR
    assert result.findings[-1].code == "qos_incompatible"


def test_healthy_topic_serializes_with_exit_code() -> None:
    result = DiagnosticEngine().analyze(
        TopicDiagnosis(
            topic_name="/joint_states",
            topic_exists=True,
            pub_count=1,
            sub_count=1,
            rate=50.0,
            message_count=50,
            sample_duration_sec=1.0,
            last_message_seen=True,
            last_message_age_ms=10.0,
        ),
        expected_rate=50.0,
    )

    payload = json.loads(result.to_json())
    assert payload["status"] == "OK"
    assert payload["exit_code"] == 0
    assert payload["findings"] == []
