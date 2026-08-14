"""CLI 入口：ros2-topic-doctor 命令行。"""

from __future__ import annotations

import argparse
import logging
import sys
import time

import rclpy
from rclpy.node import Node

from .inspector import inspect
from .sampler import Sampler
from .rules import diagnose
from .formatter import print_diagnosis
from .models import TopicDiagnosis, TopicStatus

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ros2-topic-doctor",
        description="诊断 ROS2 Topic 状态：频率、QoS、消息新鲜度等。",
    )
    parser.add_argument("topic", help="要诊断的 topic 名称")
    parser.add_argument(
        "--duration", type=float, default=3.0,
        help="采样时长（秒），默认 3",
    )
    parser.add_argument(
        "--expected-rate", type=float, default=0.0,
        help="预期频率（Hz），用于 WARN 判定",
    )
    parser.add_argument(
        "--stale-timeout", type=float, default=5000.0,
        help="消息过期阈值（ms），默认 5000",
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json",
        help="输出 JSON 格式",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="开启调试日志",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 初始化 ROS2
    rclpy.init()
    node = Node("topic_doctor")
    try:
        _run(node, args)
    finally:
        node.destroy_node()
        rclpy.shutdown()


def _run(node: Node, args) -> None:
    """执行诊断流程。"""
    topic = args.topic
    diag = TopicDiagnosis(topic_name=topic)

    # 步骤 1: 检查 topic 是否存在并收集基本信息
    diag = inspect(node, topic, diag)

    # 如果 topic 不存在，直接输出
    if diag.pub_count == 0 and diag.sub_count == 0:
        diag.status = TopicStatus.ERROR
        diag.notes.append("ERROR: Topic 不存在")
        print_diagnosis(diag, as_json=args.as_json)
        return

    # 步骤 2: 获取消息类型
    msg_type_str = _get_type_string(node, topic)
    try:
        import rosidl_runtime_py
        msg_type = rosidl_runtime_py.get_message(msg_type_str)
    except (ImportError, ValueError) as e:
        diag.msg_type = "UNKNOWN (无法加载消息类型)"
        diag.status = TopicStatus.ERROR
        diag.notes.append(f"ERROR: 无法动态加载消息类型: {e}")
        print_diagnosis(diag, as_json=args.as_json)
        return

    diag.msg_type = msg_type_str

    # 步骤 3: 采样频率
    sampler = Sampler(node, topic, msg_type, duration=args.duration)
    sample = sampler.sample()
    diag.rate = sample.rate_hz

    # 步骤 4: 计算最后消息时间（通过时间戳）
    last_age_ms = _measure_last_message_age(node, topic, msg_type, timeout_sec=2.0)
    diag.last_message_age_ms = last_age_ms

    # 步骤 5: 规则判定
    diag = diagnose(
        diag,
        stale_timeout_ms=args.stale_timeout,
        expected_rate=args.expected_rate,
    )

    # 输出
    print_diagnosis(diag, as_json=args.as_json)


def _get_type_string(node: Node, topic_name: str) -> str:
    """获取 topic 的消息类型字符串。"""
    topic_types = node.get_topic_names_and_types()
    for name, types in topic_types:
        if name == topic_name and types:
            return types[0]
    return "N/A"


def _measure_last_message_age(node: Node, topic: str, msg_type: type,
                               timeout_sec: float = 2.0) -> float:
    """测量最后一条消息的时间间隔（ms）。

    通过订阅并读取消息头中的 timestamp 来计算。
    如果消息类型没有时间戳字段，返回 0。
    """
    last_timestamp_sec = 0.0
    received = [False]

    def callback(msg):
        nonlocal last_timestamp_sec, received
        # 尝试读取 msg header timestamp
        try:
            if hasattr(msg, "header"):
                last_timestamp_sec = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
                received[0] = True
            elif hasattr(msg, "stamp"):
                last_timestamp_sec = msg.stamp.sec + msg.stamp.nanosec * 1e-9
                received[0] = True
        except Exception:
            pass

    qos = node.create_qos_profile(qos_profile_id="sensor_data")
    sub = node.create_subscription(msg_type, topic, callback, qos)

    start = time.monotonic()
    while not received[0] and (time.monotonic() - start) < timeout_sec:
        node.spin_once(timeout_sec=0.1)

    node.destroy_subscription(sub)

    if not received[0]:
        return 0.0

    now_sec = node.get_clock().now().to_msg().sec
    age_sec = now_sec - last_timestamp_sec
    return max(0.0, age_sec * 1000.0)
