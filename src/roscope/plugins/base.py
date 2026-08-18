"""Small plugin contracts kept separate from the built-in ROS collector."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from roscope.core.models import TopicDiagnosis


@runtime_checkable
class CollectorPlugin(Protocol):
    """A plugin that contributes observations to a diagnosis."""

    name: str

    def collect(self, diagnosis: TopicDiagnosis) -> None: ...


@runtime_checkable
class AnalyzerPlugin(Protocol):
    """A plugin that contributes findings after collection."""

    name: str

    def analyze(self, diagnosis: TopicDiagnosis) -> None: ...


class PluginRegistry:
    """In-process registry used by applications embedding Roscope."""

    def __init__(self) -> None:
        self.collectors: list[CollectorPlugin] = []
        self.analyzers: list[AnalyzerPlugin] = []

    def register_collector(self, plugin: CollectorPlugin) -> None:
        self.collectors.append(plugin)

    def register_analyzer(self, plugin: AnalyzerPlugin) -> None:
        self.analyzers.append(plugin)

    def apply(self, diagnosis: TopicDiagnosis) -> TopicDiagnosis:
        for plugin in self.collectors:
            plugin.collect(diagnosis)
        for plugin in self.analyzers:
            plugin.analyze(diagnosis)
        return diagnosis
