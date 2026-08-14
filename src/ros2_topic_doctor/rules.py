"""规则引擎：根据诊断数据判定 STATUS 并生成 notes。"""

from __future__ import annotations

import logging

from .models import TopicDiagnosis, TopicStatus

logger = logging.getLogger(__name__)


def evaluate(diag: TopicDiagnosis) -> TopicDiagnosis:
    """根据 diag 中的数据判定 status 和 notes。

    判定规则（按优先级从高到低）：
    ERROR:
        - pub_count == 0 且 sub_count == 0（topic 不存在）
        - rate == 0（采样期内无消息）
        - last_message_age_ms > stale_timeout_ms
    WARN:
        - rate > 0 且 expected_rate > 0 且 rate < expected_rate * 0.7
        - sub_count == 0（无消费者）
        - qos_profile_missing 非空
    OK:
        - 以上都不满足
    """
    stale_timeout_ms = diag.stale_timeout_ms

    # ERROR 检查
    if diag.pub_count == 0 and diag.sub_count == 0:
        diag.status = TopicStatus.ERROR
        diag.notes.append("ERROR: 无 Publisher 也无 Subscriber，Topic 不存在或名称错误")
        return diag

    if diag.rate == 0.0 and diag.pub_count > 0:
        diag.status = TopicStatus.ERROR
        diag.notes.append("ERROR: 有 Publisher 但采样期内无消息到达")
        return diag

    if stale_timeout_ms > 0 and diag.last_message_age_ms > stale_timeout_ms:
        diag.status = TopicStatus.ERROR
        diag.notes.append(
            f"ERROR: 消息过期 {diag.last_message_age_ms:.0f}ms，"
            f"超过阈值 {stale_timeout_ms}ms"
        )
        return diag

    # WARN 检查
    if diag.rate > 0 and diag.expected_rate > 0:
        threshold = diag.expected_rate * 0.7
        if diag.rate < threshold:
            diag.status = TopicStatus.WARN
            diag.notes.append(
                f"WARN: 实际频率 {diag.rate:.1f}Hz 低于预期 {diag.expected_rate:.1f}Hz 的 70%"
            )

    if diag.sub_count == 0 and diag.pub_count > 0:
        diag.status = TopicStatus.WARN
        diag.notes.append("WARN: 无 Subscriber，消息未被消费")

    if diag.qos_profile_missing:
        diag.status = TopicStatus.WARN
        for desc in diag.qos_profile_missing:
            diag.notes.append(f"WARN: {desc}")

    # 默认 OK
    if diag.status != TopicStatus.WARN:
        diag.status = TopicStatus.OK

    return diag


def diagnose(diag: TopicDiagnosis, *,
             stale_timeout_ms: float = 5000.0,
             expected_rate: float = 0.0) -> TopicDiagnosis:
    """便捷入口：设置参数后调用 evaluate。"""
    diag.stale_timeout_ms = stale_timeout_ms
    if expected_rate > 0:
        diag.expected_rate = expected_rate
    return evaluate(diag)
