"""Service tests with a fake collector; no ROS 2 runtime required."""

from roscope.core.models import EndpointInfo, GraphSnapshot, SampleResult, TopicSnapshot
from roscope.core.service import RoscopeService


class FakeCollector:
    def __init__(self) -> None:
        self.snapshot = TopicSnapshot(
            topic_name="/scan",
            msg_type="sensor_msgs/msg/LaserScan",
            topic_exists=True,
            publishers=[EndpointInfo(node_name="lidar")],
            subscribers=[],
        )

    def inspect_topic(self, topic_name: str) -> TopicSnapshot:
        return TopicSnapshot(
            topic_name=topic_name,
            msg_type=self.snapshot.msg_type,
            topic_exists=self.snapshot.topic_exists,
            publishers=list(self.snapshot.publishers),
            subscribers=list(self.snapshot.subscribers),
        )

    def discover_topics(self, *, include_hidden: bool = False) -> list[TopicSnapshot]:
        return [self.inspect_topic("/scan"), self.inspect_topic("/camera/image_raw")]

    def sample_topic(self, topic: TopicSnapshot, *, duration_sec: float) -> SampleResult:
        return SampleResult(
            message_count=10,
            duration_sec=duration_sec,
            rate_hz=10.0,
            last_message_age_ms=5.0,
            received=True,
        )

    def graph(self, *, include_hidden: bool = False) -> GraphSnapshot:
        return GraphSnapshot(nodes=[{"node": "/robot/driver"}])


class BatchCollector(FakeCollector):
    def __init__(self) -> None:
        super().__init__()
        self.batch_calls = 0

    def sample_topic(self, topic: TopicSnapshot, *, duration_sec: float) -> SampleResult:
        raise AssertionError("scan should use the shared observation window")

    def sample_topics(
        self, topics: list[TopicSnapshot], *, duration_sec: float
    ) -> dict[str, SampleResult]:
        self.batch_calls += 1
        return {
            topic.topic_name: SampleResult(
                message_count=1,
                duration_sec=duration_sec,
                rate_hz=1.0 / duration_sec,
                received=True,
            )
            for topic in topics
        }


def test_service_applies_samples_before_analysis() -> None:
    collector = FakeCollector()
    result = RoscopeService(collector).inspect_topic("/scan", duration_sec=1.0)

    assert result.rate == 10.0
    assert result.message_count == 10
    assert result.last_message_seen is True
    assert result.status.name == "WARN"  # publisher has no consumer


def test_scan_pattern_filters_topics() -> None:
    report = RoscopeService(FakeCollector()).scan(duration_sec=0, pattern="camera")

    assert len(report.topics) == 1
    assert report.topics[0].topic_name == "/camera/image_raw"


def test_graph_delegates_to_collector() -> None:
    graph = RoscopeService(FakeCollector()).graph()

    assert graph.nodes == [{"node": "/robot/driver"}]


def test_scan_uses_one_shared_observation_window_when_available() -> None:
    collector = BatchCollector()

    report = RoscopeService(collector).scan(duration_sec=0.5)

    assert collector.batch_calls == 1
    assert all(topic.sample_duration_sec == 0.5 for topic in report.topics)
