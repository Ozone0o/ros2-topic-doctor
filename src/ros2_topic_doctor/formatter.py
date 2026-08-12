"""格式化器：将诊断结果输出为终端文本或 JSON。"""

from __future__ import annotations

import json
import sys

from .models import TopicDiagnosis, TopicStatus


def format_text(diag: TopicDiagnosis) -> str:
    """生成清晰的终端文本输出。"""
    lines: list[str] = []

    lines.append(f"Topic:    {diag.topic_name}")
    lines.append(f"Type:     {diag.msg_type}")
    lines.append(f"Publishers: {diag.pub_count}")
    lines.append(f"Subscribers: {diag.sub_count}")

    if diag.rate > 0:
        lines.append(f"Rate:     {diag.rate:.1f} Hz")
    else:
        lines.append("Rate:     N/A")

    if diag.expected_rate > 0:
        lines.append(f"Expected: {diag.expected_rate:.1f} Hz")

    if diag.last_message_age_ms > 0:
        lines.append(f"Last msg: {diag.last_message_age_ms:.0f} ms ago")
    else:
        lines.append("Last msg: N/A")

    # QoS
    lines.append("")
    lines.append("QoS (Publisher):")
    lines.append(f"  Reliability:  {diag.qos_pub.reliability}")
    lines.append(f"  Durability:   {diag.qos_pub.durability}")
    lines.append(f"  History:      {diag.qos_pub.history}")
    lines.append(f"  Depth:        {diag.qos_pub.depth}")
    lines.append(f"  Liveliness:   {diag.qos_pub.liveliness}")

    if diag.sub_count > 0:
        lines.append("")
        lines.append("QoS (Subscriber):")
        lines.append(f"  Reliability:  {diag.qos_sub.reliability}")
        lines.append(f"  Durability:   {diag.qos_sub.durability}")
        lines.append(f"  History:      {diag.qos_sub.history}")
        lines.append(f"  Depth:        {diag.qos_sub.depth}")
        lines.append(f"  Liveliness:   {diag.qos_sub.liveliness}")

    # Status
    status_icon = {
        TopicStatus.OK: "OK",
        TopicStatus.WARN: "WARN",
        TopicStatus.ERROR: "ERROR",
    }.get(diag.status, "UNKNOWN")

    lines.append("")
    lines.append(f"Status: {status_icon}")

    for note in diag.notes:
        lines.append(f"  -> {note}")

    return "\n".join(lines)


def format_json(diag: TopicDiagnosis) -> str:
    """生成 JSON 输出。"""
    return diag.to_json()


def print_diagnosis(diag: TopicDiagnosis, *, as_json: bool = False) -> str:
    """格式化并打印诊断结果，返回字符串。"""
    if as_json:
        text = format_json(diag)
    else:
        text = format_text(diag)

    print(text)
    return text
