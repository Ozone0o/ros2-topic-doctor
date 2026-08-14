"""信息收集：通过 rclpy 查询 topic 的 publisher/subscriber/QoS 信息。"""

from __future__ import annotations

import logging
from typing import Any

from .models import QoSInfo, TopicDiagnosis, TopicStatus

logger = logging.getLogger(__name__)


def _qos_from_infospace(info: dict[str, Any]) -> QoSInfo:
    """从 get_publishers_info() 或 get_subscriptions_info() 提取 QoS。"""
    qos = QoSInfo()
    qos_profile = info.qos_profile

    # Reliability
    try:
        qos.reliability = qos_profile.reliability.name
    except Exception:
        qos.reliability = "UNKNOWN"

    # Durability
    try:
        qos.durability = qos_profile.durability.name
    except Exception:
        qos.durability = "UNKNOWN"

    # History
    try:
        qos.history = qos_profile.history.name
    except Exception:
        qos.history = "UNKNOWN"

    # Depth
    qos.depth = getattr(qos_profile, "depth", 0)

    # Liveliness
    try:
        qos.liveliness = qos_profile.liveliness.name
    except Exception:
        qos.liveliness = "UNKNOWN"

    return qos


def inspect(node, topic_name: str, diag: TopicDiagnosis) -> TopicDiagnosis:
    """收集 topic 诊断信息并填充 diag。

    查询：
    - topic 是否存在
    - message type
    - publisher / subscriber 数量
    - publisher QoS
    - subscriber QoS
    """
    # 查询所有 topic
    topic_types = node.get_topic_names_and_types()

    found = False
    for name, types in topic_types:
        if name == topic_name:
            found = True
            diag.topic_name = name
            diag.msg_type = types[0] if types else "N/A"
            break

    if not found:
        diag.topic_name = topic_name
        diag.status = TopicStatus.ERROR
        return diag

    # Publisher 信息
    pub_nodes = node.get_publishers_info_by_topic(topic_name)
    diag.pub_count = len(pub_nodes)

    if pub_nodes:
        diag.qos_pub = _qos_from_infospace(pub_nodes[0])

    # Subscriber 信息
    sub_nodes = node.get_subscriptions_info_by_topic(topic_name)
    diag.sub_count = len(sub_nodes)

    if sub_nodes:
        diag.qos_sub = _qos_from_infospace(sub_nodes[0])

    # 检查 QoS 兼容性提示
    diag.qos_profile_missing = _check_qos_mismatch(pub_nodes, sub_nodes)

    return diag


def _check_qos_mismatch(pub_infos, sub_infos) -> list[str]:
    """检查 pub/sub QoS 是否可能不兼容。"""
    notes: list[str] = []
    if not pub_infos or not sub_infos:
        return notes

    pub_qos = pub_infos[0].qos_profile
    sub_qos = sub_infos[0].qos_profile

    # Durability mismatch 常见问题
    try:
        if (getattr(pub_qos, "durability", None) is not None and
            getattr(sub_qos, "durability", None) is not None):
            if pub_qos.durability.name == "TRANSIENT_LOCAL" and \
               sub_qos.durability.name == "VOLATILE":
                notes.append(
                    "QoS: Publisher 使用 TRANSIENT_LOCAL，"
                    "Subscriber 使用 VOLATILE，可能收不到历史消息"
                )
    except Exception:
        pass

    # Reliability mismatch
    try:
        if (getattr(pub_qos, "reliability", None) is not None and
            getattr(sub_qos, "reliability", None) is not None):
            if (pub_qos.reliability.name == "BEST_EFFORT" and
                sub_qos.reliability.name == "RELIABLE"):
                notes.append(
                    "QoS: Publisher 使用 BEST_EFFORT，"
                    "Subscriber 使用 RELIABLE，可能丢消息"
                )
    except Exception:
        pass

    return notes
