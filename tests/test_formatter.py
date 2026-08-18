"""Test Roscope terminal and JSON reporters without a ROS installation."""

from __future__ import annotations

import json

from roscope.core.models import QoSInfo, TopicDiagnosis, TopicStatus
from roscope.reporters.json import format_diagnosis_json
from roscope.reporters.terminal import format_diagnosis_text


class TestFormatText:
    def test_healthy_topic(self):
        diagnosis = TopicDiagnosis(
            topic_name="/camera/image_raw",
            msg_type="sensor_msgs/msg/Image",
            pub_count=1,
            sub_count=2,
            rate=29.8,
            expected_rate=30.0,
            last_message_age_ms=34.0,
            last_message_seen=True,
            qos_pub=QoSInfo(
                reliability="BEST_EFFORT",
                durability="VOLATILE",
                history="DEFAULT",
                depth=5,
                liveliness="DEFAULT",
            ),
            qos_sub=QoSInfo(
                reliability="BEST_EFFORT",
                durability="VOLATILE",
                history="DEFAULT",
                depth=5,
                liveliness="DEFAULT",
            ),
            status=TopicStatus.OK,
        )
        text = format_diagnosis_text(diagnosis, color=False)

        assert "/camera/image_raw" in text
        assert "sensor_msgs/msg/Image" in text
        assert "Publishers    1" in text
        assert "Subscribers   2" in text
        assert "29.80 Hz" in text
        assert "34 ms ago" in text
        assert "Status        OK" in text
        assert "BEST_EFFORT" in text

    def test_error_topic_not_found(self):
        diagnosis = TopicDiagnosis(topic_name="/nonexistent", status=TopicStatus.ERROR)
        text = format_diagnosis_text(diagnosis, color=False)
        assert "Status        ERROR" in text
        assert "/nonexistent" in text

    def test_no_rate_when_zero(self):
        diagnosis = TopicDiagnosis(
            topic_name="/empty_topic",
            pub_count=1,
            sub_count=0,
            rate=0.0,
            status=TopicStatus.ERROR,
        )
        text = format_diagnosis_text(diagnosis, color=False)
        assert "no samples" in text

    def test_no_subscriber_qos_skipped(self):
        diagnosis = TopicDiagnosis(
            topic_name="/scan",
            pub_count=1,
            sub_count=0,
            rate=10.0,
            qos_pub=QoSInfo(reliability="RELIABLE", depth=10),
            status=TopicStatus.WARN,
        )
        text = format_diagnosis_text(diagnosis, color=False)
        assert "Publisher QoS:" in text
        assert "Subscriber QoS:" not in text


class TestFormatJson:
    def test_json_output(self):
        diagnosis = TopicDiagnosis(
            topic_name="/camera/image_raw",
            msg_type="sensor_msgs/msg/Image",
            pub_count=1,
            sub_count=2,
            rate=29.8,
            expected_rate=30.0,
            last_message_age_ms=34.0,
            qos_pub=QoSInfo(reliability="BEST_EFFORT", durability="VOLATILE", depth=5),
            status=TopicStatus.OK,
        )
        data = json.loads(format_diagnosis_json(diagnosis))

        assert data["topic_name"] == "/camera/image_raw"
        assert data["msg_type"] == "sensor_msgs/msg/Image"
        assert data["pub_count"] == 1
        assert data["sub_count"] == 2
        assert data["rate"] == 29.8
        assert data["status"] == "OK"
        assert data["qos_pub"]["reliability"] == "BEST_EFFORT"

    def test_json_error_status(self):
        diagnosis = TopicDiagnosis(topic_name="/missing", status=TopicStatus.ERROR)
        data = json.loads(format_diagnosis_json(diagnosis))
        assert data["status"] == "ERROR"
