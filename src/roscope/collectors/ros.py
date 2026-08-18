"""ROS 2 graph and message collector.

No ROS package is imported at module import time.  This is important for
``roscope --help``, documentation builds, and CI jobs that intentionally run
without a sourced ROS distribution.
"""

from __future__ import annotations

import time
from typing import Any

from roscope.core.models import (
    EndpointInfo,
    GraphSnapshot,
    SampleResult,
    TopicSnapshot,
    qos_info_from_profile,
)


class RosUnavailableError(RuntimeError):
    """Raised when a ROS-backed command is run outside a ROS 2 environment."""


class RosRuntime:
    """Own the lifecycle of a short-lived rclpy node."""

    def __init__(self, *, node_name: str = "roscope") -> None:
        self.node_name = node_name
        self.rclpy: Any = None
        self.node: Any = None
        self._owns_init = False

    def __enter__(self) -> RosRuntime:
        try:
            import rclpy
            from rclpy.node import Node
        except ImportError as exc:
            raise RosUnavailableError(
                "ROS 2 Python bindings are unavailable. Source a ROS 2 distribution "
                "before running a graph command."
            ) from exc

        self.rclpy = rclpy
        try:
            already_running = bool(rclpy.ok())
        except Exception:
            already_running = False
        if not already_running:
            rclpy.init(args=None)
            self._owns_init = True
        self.node = Node(self.node_name)
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.node is not None:
            self.node.destroy_node()
            self.node = None
        if self._owns_init and self.rclpy is not None:
            try:
                if self.rclpy.ok():
                    self.rclpy.shutdown()
            except Exception:
                pass


class RosCollector:
    """Collect topic and graph facts from an active :class:`RosRuntime`."""

    def __init__(self, runtime: RosRuntime) -> None:
        if runtime.node is None or runtime.rclpy is None:
            raise ValueError("RosCollector requires an active RosRuntime")
        self.runtime = runtime
        self.node = runtime.node
        self.rclpy = runtime.rclpy
        # Use the actual endpoint profile for the temporary observer whenever
        # discovery exposes it. A sensor-data profile is only a fallback.
        self._publisher_qos_profiles: dict[str, tuple[Any, ...]] = {}

    def discover_topics(self, *, include_hidden: bool = False) -> list[TopicSnapshot]:
        return [
            self.inspect_topic(topic_name, include_hidden=include_hidden)
            for topic_name, _ in self._topic_names_and_types()
            if include_hidden or not _is_hidden(topic_name)
        ]

    def inspect_topic(
        self,
        topic_name: str,
        *,
        include_hidden: bool = True,
    ) -> TopicSnapshot:
        topic_types = dict(self._topic_names_and_types())
        msg_types = topic_types.get(topic_name, [])
        exists = topic_name in topic_types
        msg_type = msg_types[0] if msg_types else "N/A"
        if not include_hidden and _is_hidden(topic_name):
            exists = False

        publisher_infos = self._get_endpoint_info(topic_name, publishers=True)
        publishers = self._endpoints(publisher_infos, msg_type)
        subscribers = self._endpoints(
            self._get_endpoint_info(topic_name, publishers=False),
            msg_type,
        )
        if publisher_infos:
            self._publisher_qos_profiles[topic_name] = tuple(
                profile
                for profile in (getattr(info, "qos_profile", None) for info in publisher_infos)
                if profile is not None
            )
        return TopicSnapshot(
            topic_name=topic_name,
            msg_type=msg_type,
            topic_exists=exists,
            publishers=publishers,
            subscribers=subscribers,
            qos_issues=_qos_issues(publishers, subscribers),
        )

    def sample_topic(self, topic: TopicSnapshot, *, duration_sec: float) -> SampleResult:
        return self.sample_topics([topic], duration_sec=duration_sec).get(
            topic.topic_name, SampleResult()
        )

    def sample_topics(
        self, topics: list[TopicSnapshot], *, duration_sec: float
    ) -> dict[str, SampleResult]:
        """Sample all topics during one shared observation window.

        One subscription is created per topic and the node is spun once for
        the complete window. This keeps ``scan`` runtime close to
        ``duration_sec`` instead of multiplying it by the number of topics.
        """
        if duration_sec <= 0:
            return {}
        try:
            from rclpy.qos import qos_profile_sensor_data
            from rosidl_runtime_py.utilities import get_message
        except ImportError as exc:
            raise RuntimeError(
                "message introspection dependencies are unavailable; "
                "source the ROS 2 interface packages"
            ) from exc

        counts = {topic.topic_name: 0 for topic in topics}
        last_received = {topic.topic_name: 0.0 for topic in topics}
        subscriptions: list[Any] = []
        qos_sources: dict[str, str] = {}

        for topic in topics:
            if topic.msg_type in ("", "N/A"):
                for subscription in subscriptions:
                    self.node.destroy_subscription(subscription)
                raise RuntimeError(f"message type is unavailable for {topic.topic_name}")
            try:
                message_type = get_message(topic.msg_type)
            except (ImportError, AttributeError, ModuleNotFoundError, ValueError) as exc:
                for subscription in subscriptions:
                    self.node.destroy_subscription(subscription)
                raise RuntimeError(f"unable to load message type {topic.msg_type}: {exc}") from exc

            qos_profile, qos_source = self._observer_qos(topic.topic_name, qos_profile_sensor_data)

            def callback(_message: Any, topic_name: str = topic.topic_name) -> None:
                counts[topic_name] += 1
                last_received[topic_name] = time.monotonic()

            try:
                subscriptions.append(
                    self.node.create_subscription(
                        message_type,
                        topic.topic_name,
                        callback,
                        qos_profile,
                    )
                )
            except Exception as exc:
                for subscription in subscriptions:
                    self.node.destroy_subscription(subscription)
                raise RuntimeError(f"unable to subscribe to {topic.topic_name}: {exc}") from exc
            qos_sources[topic.topic_name] = qos_source

        started = time.monotonic()
        try:
            while time.monotonic() - started < duration_sec:
                self.rclpy.spin_once(self.node, timeout_sec=0.1)
        finally:
            for subscription in subscriptions:
                self.node.destroy_subscription(subscription)

        elapsed = max(time.monotonic() - started, 1e-9)
        now = time.monotonic()
        return {
            topic.topic_name: SampleResult(
                message_count=counts[topic.topic_name],
                duration_sec=round(elapsed, 3),
                rate_hz=round(counts[topic.topic_name] / elapsed, 2),
                last_message_age_ms=round((now - last_received[topic.topic_name]) * 1000, 1)
                if counts[topic.topic_name]
                else 0.0,
                received=counts[topic.topic_name] > 0,
                qos_source=qos_sources[topic.topic_name],
            )
            for topic in topics
        }

    def _observer_qos(self, topic_name: str, fallback: Any) -> tuple[Any, str]:
        profiles = self._publisher_qos_profiles.get(topic_name, ())
        if not profiles:
            return fallback, "sensor_data_fallback"

        # BEST_EFFORT + VOLATILE is the least demanding observer profile and
        # is compatible with both common publisher profiles when available.
        selected = next(
            (
                profile
                for profile in profiles
                if "BEST_EFFORT" in _policy_name(getattr(profile, "reliability", None))
                and "VOLATILE" in _policy_name(getattr(profile, "durability", None))
            ),
            profiles[0],
        )
        return selected, f"publisher_endpoints:{len(profiles)}"

    def graph(self, *, include_hidden: bool = False) -> GraphSnapshot:
        nodes = [
            {"name": name, "namespace": namespace, "node": _qualified_node(namespace, name)}
            for name, namespace in self.node.get_node_names_and_namespaces()
        ]
        topics = []
        for topic_name, types in self._topic_names_and_types():
            if not include_hidden and _is_hidden(topic_name):
                continue
            publishers = self._get_endpoint_info(topic_name, publishers=True)
            subscribers = self._get_endpoint_info(topic_name, publishers=False)
            topics.append(
                {
                    "name": topic_name,
                    "type": types[0] if types else "N/A",
                    "publishers": len(publishers),
                    "subscribers": len(subscribers),
                }
            )
        return GraphSnapshot(nodes=nodes, topics=topics)

    def _topic_names_and_types(self) -> list[tuple[str, list[str]]]:
        try:
            return list(self.node.get_topic_names_and_types(no_demangle=True))
        except TypeError:
            return list(self.node.get_topic_names_and_types())

    def _get_endpoint_info(self, topic_name: str, *, publishers: bool) -> list[Any]:
        method_name = (
            "get_publishers_info_by_topic" if publishers else "get_subscriptions_info_by_topic"
        )
        method = getattr(self.node, method_name)
        try:
            return list(method(topic_name, no_mangle=False))
        except TypeError:
            return list(method(topic_name))

    @staticmethod
    def _endpoints(infos: list[Any], default_type: str) -> list[EndpointInfo]:
        endpoints = []
        for info in infos:
            endpoints.append(
                EndpointInfo(
                    node_name=str(getattr(info, "node_name", "")),
                    node_namespace=str(getattr(info, "node_namespace", "")),
                    topic_type=str(getattr(info, "topic_type", default_type)),
                    qos=qos_info_from_profile(getattr(info, "qos_profile", None)),
                )
            )
        return endpoints


def _qos_issues(publishers: list[EndpointInfo], subscribers: list[EndpointInfo]) -> list[str]:
    """Apply the DDS offered/requested rules to discovered endpoints."""

    issues: list[str] = []
    for publisher in publishers:
        for subscriber in subscribers:
            pub_qos = publisher.qos
            sub_qos = subscriber.qos
            if pub_qos.reliability == "BEST_EFFORT" and sub_qos.reliability == "RELIABLE":
                issues.append(
                    "Incompatible reliability: publisher is BEST_EFFORT but "
                    "subscriber requests RELIABLE"
                )
            if pub_qos.durability == "VOLATILE" and sub_qos.durability == "TRANSIENT_LOCAL":
                issues.append(
                    "Incompatible durability: publisher is VOLATILE but "
                    "subscriber requests TRANSIENT_LOCAL"
                )
    return list(dict.fromkeys(issues))


def _is_hidden(topic_name: str) -> bool:
    return any(part.startswith("_") for part in topic_name.split("/") if part)


def _qualified_node(namespace: str, name: str) -> str:
    namespace = namespace.rstrip("/")
    return f"{namespace}/{name}" if namespace else name


def _policy_name(value: Any) -> str:
    return str(getattr(value, "name", value)).upper()
