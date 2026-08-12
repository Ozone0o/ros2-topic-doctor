"""测试 formatter 模块——脱离 ROS2。"""

import json
import pytest
from ros2_topic_doctor.models import TopicDiagnosis, TopicStatus, QoSInfo
from ros2_topic_doctor.formatter import format_text, format_json


class TestFormatText:
    """终端文本格式测试。"""

    def test_healthy_topic(self):
        diag = TopicDiagnosis(
            topic_name="/camera/image_raw",
            msg_type="sensor_msgs/msg/Image",
            pub_count=1, sub_count=2,
            rate=29.8, expected_rate=30.0,
            last_message_age_ms=34.0,
            qos_pub=QoSInfo(reliability="BEST_EFFORT", durability="VOLATILE",
                           history="DEFAULT", depth=5, liveliness="DEFAULT"),
            qos_sub=QoSInfo(reliability="BEST_EFFORT", durability="VOLATILE",
                           history="DEFAULT", depth=5, liveliness="DEFAULT"),
            status=TopicStatus.OK,
        )
        text = format_text(diag)

        assert "/camera/image_raw" in text
        assert "sensor_msgs/msg/Image" in text
        assert "Publishers: 1" in text
        assert "Subscribers: 2" in text
        assert "29.8 Hz" in text
        assert "Expected: 30.0 Hz" in text
        assert "34 ms ago" in text
        assert "Status: OK" in text
        assert "BEST_EFFORT" in text

    def test_error_topic_not_found(self):
        diag = TopicDiagnosis(
            topic_name="/nonexistent",
            status=TopicStatus.ERROR,
            notes=["ERROR: Topic 不存在"],
        )
        text = format_text(diag)
        assert "Status: ERROR" in text
        assert "/nonexistent" in text

    def test_no_rate_when_zero(self):
        diag = TopicDiagnosis(
            topic_name="/empty_topic",
            pub_count=1, sub_count=0,
            rate=0.0,
            status=TopicStatus.ERROR,
            notes=["ERROR: 有 Publisher 但采样期内无消息到达"],
        )
        text = format_text(diag)
        assert "N/A" in text

    def test_warn_status(self):
        diag = TopicDiagnosis(
            topic_name="/scan",
            pub_count=1, sub_count=0,
            rate=10.0, expected_rate=30.0,
            status=TopicStatus.WARN,
            notes=["WARN: 无 Subscriber"],
        )
        text = format_text(diag)
        assert "Status: WARN" in text

    def test_no_subscriber_qos_skipped(self):
        diag = TopicDiagnosis(
            topic_name="/scan",
            pub_count=1, sub_count=0,
            rate=10.0,
            qos_pub=QoSInfo(reliability="RELIABLE", depth=10),
            status=TopicStatus.WARN,
        )
        text = format_text(diag)
        assert "QoS (Publisher)" in text
        # 没有 subscriber，不应出现 Subscriber QoS
        assert "QoS (Subscriber)" not in text


class TestFormatJson:
    """JSON 格式测试。"""

    def test_json_output(self):
        diag = TopicDiagnosis(
            topic_name="/camera/image_raw",
            msg_type="sensor_msgs/msg/Image",
            pub_count=1, sub_count=2,
            rate=29.8, expected_rate=30.0,
            last_message_age_ms=34.0,
            qos_pub=QoSInfo(reliability="BEST_EFFORT", durability="VOLATILE",
                           history="DEFAULT", depth=5, liveliness="DEFAULT"),
            status=TopicStatus.OK,
        )
        text = format_json(diag)
        data = json.loads(text)

        assert data["topic_name"] == "/camera/image_raw"
        assert data["msg_type"] == "sensor_msgs/msg/Image"
        assert data["pub_count"] == 1
        assert data["sub_count"] == 2
        assert data["rate"] == 29.8
        assert data["status"] == "OK"
        assert data["qos_pub"]["reliability"] == "BEST_EFFORT"

    def test_json_error_status(self):
        diag = TopicDiagnosis(
            topic_name="/missing",
            pub_count=0, sub_count=0,
            status=TopicStatus.ERROR,
            notes=["ERROR: Topic 不存在"],
        )
        data = json.loads(format_json(diag))
        assert data["status"] == "ERROR"
