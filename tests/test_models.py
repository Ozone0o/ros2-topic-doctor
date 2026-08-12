"""测试 models 模块。"""

import json
import pytest
from ros2_topic_doctor.models import TopicDiagnosis, TopicStatus, QoSInfo, SampleResult


class TestQoSInfo:
    def test_defaults(self):
        qos = QoSInfo()
        assert qos.reliability == "UNKNOWN"
        assert qos.depth == 0

    def test_to_dict(self):
        qos = QoSInfo(reliability="RELIABLE", durability="TRANSIENT_LOCAL", depth=10)
        d = qos.to_dict()
        assert d["reliability"] == "RELIABLE"
        assert d["depth"] == 10


class TestSampleResult:
    def test_defaults(self):
        s = SampleResult()
        assert s.rate_hz == 0.0

    def test_to_dict(self):
        s = SampleResult(message_count=30, duration_sec=1.0, rate_hz=30.0)
        d = s.to_dict()
        assert d["message_count"] == 30


class TestTopicDiagnosis:
    def test_defaults(self):
        diag = TopicDiagnosis(topic_name="/test")
        assert diag.status == TopicStatus.OK
        assert diag.notes == []

    def test_to_dict(self):
        diag = TopicDiagnosis(topic_name="/scan", pub_count=1, sub_count=2, rate=10.0)
        d = diag.to_dict()
        assert d["topic_name"] == "/scan"
        assert d["status"] == "OK"

    def test_to_json(self):
        diag = TopicDiagnosis(topic_name="/scan", pub_count=1, status=TopicStatus.WARN)
        text = diag.to_json()
        data = json.loads(text)
        assert data["topic_name"] == "/scan"
        assert data["status"] == "WARN"

    def test_to_json_indent(self):
        diag = TopicDiagnosis(topic_name="/test")
        # 应该能正常序列化不带缩进
        text = diag.to_json(indent=None)
        data = json.loads(text)
        assert data["topic_name"] == "/test"
