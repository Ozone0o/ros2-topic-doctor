"""Demo: 演示 ros2-topic-doctor 的诊断规则判定。

不依赖真实 ROS2 环境，直接使用 rules 模块测试各种 topic 状态。

用法:
    python examples/demo.py
"""

from __future__ import annotations

from ros2_topic_doctor.models import TopicDiagnosis, TopicStatus
from ros2_topic_doctor.rules import diagnose


def status_label(s: TopicStatus) -> str:
    return {TopicStatus.OK: "OK", TopicStatus.WARN: "WARN", TopicStatus.ERROR: "ERROR"}[s]


def main() -> None:
    print("ros2-topic-doctor 诊断规则演示")
    print("=" * 50)

    test_cases = [
        {
            "desc": "健康 topic",
            "diag": TopicDiagnosis(topic_name="/joint_states", pub_count=1, sub_count=2,
                                   rate=50.0, expected_rate=50.0, last_message_age_ms=10.0),
        },
        {
            "desc": "Topic 不存在",
            "diag": TopicDiagnosis(topic_name="/fake/topic", pub_count=0, sub_count=0),
        },
        {
            "desc": "频率过低",
            "diag": TopicDiagnosis(topic_name="/scan", pub_count=1, sub_count=1,
                                   rate=5.0, expected_rate=30.0),
        },
        {
            "desc": "消息过期",
            "diag": TopicDiagnosis(topic_name="/scan", pub_count=1, sub_count=1,
                                   rate=10.0, last_message_age_ms=10000.0),
        },
        {
            "desc": "无订阅者",
            "diag": TopicDiagnosis(topic_name="/camera/image_raw", pub_count=1, sub_count=0,
                                   rate=30.0),
        },
    ]

    for tc in test_cases:
        result = diagnose(tc["diag"], stale_timeout_ms=5000.0, expected_rate=tc["diag"].expected_rate or 30.0)
        notes = "; ".join(result.notes) if result.notes else "-"
        print(f"\n  {tc['desc']}")
        print(f"    状态: {status_label(result.status)}")
        print(f"    频率: {result.rate or 0:.1f} Hz")
        print(f"    备注: {notes}")


if __name__ == "__main__":
    main()
