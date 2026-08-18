"""Protocols for collector plugins.

Collectors are deliberately small: they report facts and never decide whether
those facts are healthy.  A simulator, bag reader, or remote DDS collector can
implement these protocols without depending on the terminal CLI.
"""

from __future__ import annotations

from typing import Protocol

from roscope.core.models import GraphSnapshot, SampleResult, TopicSnapshot


class Collector(Protocol):
    def inspect_topic(self, topic_name: str) -> TopicSnapshot: ...

    def discover_topics(self, *, include_hidden: bool = False) -> list[TopicSnapshot]: ...

    def sample_topic(self, topic: TopicSnapshot, *, duration_sec: float) -> SampleResult: ...

    def graph(self, *, include_hidden: bool = False) -> GraphSnapshot: ...
