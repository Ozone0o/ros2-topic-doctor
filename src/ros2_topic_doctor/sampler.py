"""数据采样：订阅 topic 并统计频率。"""

from __future__ import annotations

import logging
import time
from typing import Callable

from .models import SampleResult

logger = logging.getLogger(__name__)


class Sampler:
    """在指定窗口内订阅 topic 并统计消息数量。"""

    def __init__(self, node, topic_name: str, msg_type: type,
                 duration: float = 3.0, qos_overrides: dict | None = None):
        self._node = node
        self._topic_name = topic_name
        self._msg_type = msg_type
        self._duration = duration
        self._qos_overrides = qos_overrides
        self._count = 0
        self._callback: Callable | None = None

    def sample(self) -> SampleResult:
        """采样 duration 秒，返回 SampleResult。"""
        self._count = 0
        start = time.monotonic()

        # 创建临时订阅
        qos = self._node.create_qos_profile(
            qos_profile_id="sensor_data",
            overrides=self._qos_overrides,
        )
        sub = self._node.create_subscription(
            self._msg_type,
            self._topic_name,
            self._on_message,
            qos,
        )

        try:
            # 运行 spin 直到超时
            while self._elapsed(start) < self._duration:
                self._node.spin_once(timeout_sec=0.1)
        finally:
            self._node.destroy_subscription(sub)

        duration = self._elapsed(start)
        rate = self._count / duration if duration > 0 else 0.0

        return SampleResult(
            message_count=self._count,
            duration_sec=round(duration, 3),
            rate_hz=round(rate, 2),
        )

    def _on_message(self, msg):
        self._count += 1

    def _elapsed(self, start: float) -> float:
        return time.monotonic() - start
