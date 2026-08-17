"""测试 rules 模块——完全脱离 ROS2。"""

import pytest
from ros2_topic_doctor.models import TopicDiagnosis, TopicStatus, QoSInfo
from ros2_topic_doctor.rules import diagnose, evaluate


class TestDiagnose:
    """判定规则单元测试。"""

    def test_topic_not_found(self):
        diag = TopicDiagnosis(topic_name="/fake/topic", pub_count=0, sub_count=0)
        result = diagnose(diag, stale_timeout_ms=5000.0)
        assert result.status == TopicStatus.ERROR
        assert any("不存在" in n for n in result.notes)

    def test_no_message_received(self):
        diag = TopicDiagnosis(topic_name="/camera/image_raw", pub_count=1, sub_count=1,
                              rate=0.0)
        result = diagnose(diag, stale_timeout_ms=5000.0)
        assert result.status == TopicStatus.ERROR
        assert any("无消息到达" in n for n in result.notes)

    def test_stale_message(self):
        diag = TopicDiagnosis(topic_name="/scan", pub_count=1, sub_count=1,
                              rate=10.0, last_message_age_ms=10000.0)
        result = diagnose(diag, stale_timeout_ms=5000.0)
        assert result.status == TopicStatus.ERROR
        assert any("过期" in n for n in result.notes)

    def test_rate_too_low(self):
        diag = TopicDiagnosis(topic_name="/scan", pub_count=1, sub_count=1,
                              rate=5.0, expected_rate=30.0)
        result = diagnose(diag, stale_timeout_ms=5000.0)
        assert result.status == TopicStatus.WARN
        assert any("频率" in n for n in result.notes)

    def test_no_subscriber(self):
        diag = TopicDiagnosis(topic_name="/camera/image_raw", pub_count=1, sub_count=0,
                              rate=30.0)
        result = diagnose(diag, stale_timeout_ms=5000.0)
        assert result.status == TopicStatus.WARN
        assert any("Subscriber" in n for n in result.notes)

    def test_qos_mismatch_warning(self):
        diag = TopicDiagnosis(topic_name="/scan", pub_count=1, sub_count=1,
                              rate=10.0, qos_profile_missing=["QoS 不兼容提示"])
        result = diagnose(diag, stale_timeout_ms=5000.0)
        assert result.status == TopicStatus.WARN
        assert any("QoS" in n for n in result.notes)

    def test_healthy_topic(self):
        diag = TopicDiagnosis(topic_name="/joint_states", pub_count=1, sub_count=2,
                              rate=50.0, expected_rate=50.0, last_message_age_ms=10.0)
        result = diagnose(diag, stale_timeout_ms=5000.0)
        assert result.status == TopicStatus.OK
        assert diag.expected_rate == 50.0

    def test_stale_overrides_warn(self):
        """过期应覆盖低频的 WARN，升级为 ERROR。"""
        diag = TopicDiagnosis(topic_name="/scan", pub_count=1, sub_count=1,
                              rate=5.0, expected_rate=30.0, last_message_age_ms=10000.0)
        result = diagnose(diag, stale_timeout_ms=5000.0)
        assert result.status == TopicStatus.ERROR

    def test_multiple_notes(self):
        """低频 + 无 subscriber 应产生多条 note。"""
        diag = TopicDiagnosis(topic_name="/fake", pub_count=1, sub_count=0,
                              rate=5.0, expected_rate=30.0)
        result = diagnose(diag, stale_timeout_ms=5000.0)
        assert result.status == TopicStatus.WARN
        assert len(result.notes) >= 2


class TestEvaluate:
    """evaluate 直接测试（不设置参数）。"""

    def test_error_when_no_pub_no_sub(self):
        diag = TopicDiagnosis(pub_count=0, sub_count=0)
        result = evaluate(diag)
        assert result.status == TopicStatus.ERROR

    def test_ok_when_normal(self):
        diag = TopicDiagnosis(pub_count=1, sub_count=1, rate=30.0,
                              expected_rate=30.0, last_message_age_ms=10.0,
                              stale_timeout_ms=5000.0)
        result = evaluate(diag)
        assert result.status == TopicStatus.OK
