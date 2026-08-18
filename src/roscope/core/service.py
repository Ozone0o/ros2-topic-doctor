"""Use-case orchestration shared by all Roscope CLI commands."""

from __future__ import annotations

import time
from typing import Protocol

from .engine import DiagnosticEngine
from .models import (
    GraphSnapshot,
    QoSInfo,
    SampleResult,
    ScanReport,
    TopicDiagnosis,
    TopicSnapshot,
)


class Collector(Protocol):
    def inspect_topic(self, topic_name: str) -> TopicSnapshot: ...

    def discover_topics(self, *, include_hidden: bool = False) -> list[TopicSnapshot]: ...

    def sample_topic(self, topic: TopicSnapshot, *, duration_sec: float) -> SampleResult: ...

    def sample_topics(
        self, topics: list[TopicSnapshot], *, duration_sec: float
    ) -> dict[str, SampleResult]: ...

    def graph(self, *, include_hidden: bool = False) -> GraphSnapshot: ...


class RoscopeService:
    """Coordinate collection and analysis without knowing about terminals."""

    def __init__(self, collector: Collector, engine: DiagnosticEngine | None = None) -> None:
        self.collector = collector
        self.engine = engine or DiagnosticEngine()

    def inspect_topic(
        self,
        topic_name: str,
        *,
        duration_sec: float = 3.0,
        expected_rate: float = 0.0,
        stale_timeout_ms: float = 5000.0,
    ) -> TopicDiagnosis:
        snapshot = self.collector.inspect_topic(topic_name)
        diagnosis = self._diagnosis_from_snapshot(snapshot)
        if snapshot.topic_exists and snapshot.pub_count > 0 and duration_sec > 0:
            try:
                sample = self.collector.sample_topic(snapshot, duration_sec=duration_sec)
                self._apply_sample(diagnosis, sample)
            except Exception as exc:  # Collector adapters expose useful context.
                diagnosis.collection_errors.append(str(exc))
        return self.engine.analyze(
            diagnosis,
            expected_rate=expected_rate,
            stale_timeout_ms=stale_timeout_ms,
        )

    def scan(
        self,
        *,
        duration_sec: float = 0.5,
        expected_rate: float = 0.0,
        stale_timeout_ms: float = 5000.0,
        include_hidden: bool = False,
        pattern: str | None = None,
    ) -> ScanReport:
        started = time.monotonic()
        snapshots = self.collector.discover_topics(include_hidden=include_hidden)
        if pattern:
            snapshots = [snapshot for snapshot in snapshots if pattern in snapshot.topic_name]
        batch_sampler = getattr(self.collector, "sample_topics", None)
        batch_samples: dict[str, SampleResult] = {}
        batch_error: str | None = None
        batch_targets = [
            snapshot for snapshot in snapshots if snapshot.topic_exists and snapshot.pub_count > 0
        ]
        batch_sampling = callable(batch_sampler) and duration_sec > 0 and bool(batch_targets)
        if batch_sampling:
            try:
                batch_samples = dict(batch_sampler(batch_targets, duration_sec=duration_sec))
            except Exception as exc:
                batch_error = str(exc)
        topics = [
            self._inspect_snapshot(
                snapshot,
                duration_sec=duration_sec,
                expected_rate=expected_rate,
                stale_timeout_ms=stale_timeout_ms,
                sample=batch_samples.get(snapshot.topic_name),
                batch_sampling=batch_sampling,
                batch_error=batch_error,
            )
            for snapshot in snapshots
        ]
        topics.sort(key=lambda topic: (-int(topic.status), topic.topic_name))
        return ScanReport(topics=topics, duration_sec=round(time.monotonic() - started, 3))

    def graph(self, *, include_hidden: bool = False) -> GraphSnapshot:
        return self.collector.graph(include_hidden=include_hidden)

    def _inspect_snapshot(
        self,
        snapshot: TopicSnapshot,
        *,
        duration_sec: float,
        expected_rate: float,
        stale_timeout_ms: float,
        sample: SampleResult | None = None,
        batch_sampling: bool = False,
        batch_error: str | None = None,
    ) -> TopicDiagnosis:
        diagnosis = self._diagnosis_from_snapshot(snapshot)
        if snapshot.topic_exists and snapshot.pub_count > 0 and duration_sec > 0:
            if sample is not None:
                self._apply_sample(diagnosis, sample)
            elif batch_sampling:
                if batch_error:
                    diagnosis.collection_errors.append(batch_error)
            else:
                try:
                    self._apply_sample(
                        diagnosis,
                        self.collector.sample_topic(snapshot, duration_sec=duration_sec),
                    )
                except Exception as exc:
                    diagnosis.collection_errors.append(str(exc))
        return self.engine.analyze(
            diagnosis,
            expected_rate=expected_rate,
            stale_timeout_ms=stale_timeout_ms,
        )

    @staticmethod
    def _diagnosis_from_snapshot(snapshot: TopicSnapshot) -> TopicDiagnosis:
        return TopicDiagnosis(
            topic_name=snapshot.topic_name,
            msg_type=snapshot.msg_type,
            topic_exists=snapshot.topic_exists,
            pub_count=snapshot.pub_count,
            sub_count=snapshot.sub_count,
            qos_pub=snapshot.publishers[0].qos if snapshot.publishers else QoSInfo(),
            qos_sub=snapshot.subscribers[0].qos if snapshot.subscribers else QoSInfo(),
            publishers=list(snapshot.publishers),
            subscribers=list(snapshot.subscribers),
            qos_issues=list(snapshot.qos_issues),
        )

    @staticmethod
    def _apply_sample(diagnosis: TopicDiagnosis, sample: SampleResult) -> None:
        diagnosis.message_count = sample.message_count
        diagnosis.sample_duration_sec = sample.duration_sec
        diagnosis.rate = sample.rate_hz
        diagnosis.last_message_age_ms = sample.last_message_age_ms
        diagnosis.last_message_seen = sample.received
        diagnosis.observation_qos = sample.qos_source
