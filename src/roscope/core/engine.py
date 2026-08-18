"""Actionable diagnostic rules for ROS 2 communication health."""

from __future__ import annotations

from .models import Finding, TopicDiagnosis, TopicStatus


class DiagnosticEngine:
    """Turn observations into prioritized, actionable findings.

    The engine is intentionally independent from ROS 2.  Collectors provide
    facts; this class explains what those facts mean.  That separation makes
    the rules deterministic in unit tests and lets plugins add observations in
    the future without coupling them to the terminal UI.
    """

    def __init__(self, *, rate_warn_threshold: float = 0.7) -> None:
        if not 0 < rate_warn_threshold <= 1:
            raise ValueError("rate_warn_threshold must be between 0 and 1")
        self.rate_warn_threshold = rate_warn_threshold

    def analyze(
        self,
        diagnosis: TopicDiagnosis,
        *,
        expected_rate: float | None = None,
        stale_timeout_ms: float = 5000.0,
    ) -> TopicDiagnosis:
        """Evaluate a diagnosis and populate findings in severity order."""

        if expected_rate is not None and expected_rate > 0:
            diagnosis.expected_rate = expected_rate
        diagnosis.stale_timeout_ms = stale_timeout_ms
        diagnosis.findings.clear()
        diagnosis.notes.clear()
        diagnosis.status = TopicStatus.OK

        self._missing_or_unconnected(diagnosis)
        self._collection_error(diagnosis)
        self._publisher_health(diagnosis)
        self._freshness(diagnosis)
        self._frequency(diagnosis)
        self._subscriber_health(diagnosis)
        self._qos(diagnosis)
        self._type_consistency(diagnosis)

        for finding in diagnosis.findings:
            diagnosis.notes.append(
                f"{finding.severity.name}: {finding.problem}"
                + (f" — {finding.detail}" if finding.detail else "")
            )
        if not diagnosis.findings:
            diagnosis.status = TopicStatus.OK
        return diagnosis

    def _missing_or_unconnected(self, diagnosis: TopicDiagnosis) -> None:
        missing = diagnosis.pub_count == 0 and diagnosis.sub_count == 0
        if missing:
            self._add(
                diagnosis,
                code="topic_missing",
                severity=TopicStatus.ERROR,
                problem="Topic is missing",
                detail=f"No publisher or subscriber was discovered for {diagnosis.topic_name}.",
                causes=[
                    "The topic name or namespace is incorrect.",
                    "The node that owns the topic is not running.",
                    "The ROS domain or DDS discovery network is different.",
                ],
                commands=[
                    "roscope graph",
                    "ros2 topic list",
                    f"ros2 topic info -v {diagnosis.topic_name}",
                ],
                evidence={"publishers": diagnosis.pub_count, "subscribers": diagnosis.sub_count},
            )
        elif diagnosis.pub_count == 0 and diagnosis.sub_count > 0:
            self._add(
                diagnosis,
                code="subscriber_waiting",
                severity=TopicStatus.ERROR,
                problem="Subscribers are waiting for a publisher",
                detail=(
                    f"{diagnosis.sub_count} subscriber(s) are present, but no "
                    "publisher is visible."
                ),
                causes=[
                    "The driver or upstream node has not started.",
                    "The publisher crashed after the subscriber connected.",
                    "DDS discovery is incomplete across the participating machines.",
                ],
                commands=[
                    "roscope graph",
                    "ros2 node list",
                    f"ros2 topic info -v {diagnosis.topic_name}",
                ],
                evidence={"publishers": 0, "subscribers": diagnosis.sub_count},
            )

    def _collection_error(self, diagnosis: TopicDiagnosis) -> None:
        if not diagnosis.collection_errors:
            return
        self._add(
            diagnosis,
            code="collection_error",
            severity=TopicStatus.ERROR,
            problem="Roscope could not observe this topic",
            detail="; ".join(diagnosis.collection_errors),
            causes=[
                "The message package is not sourced in this environment.",
                "The topic type is not available to rosidl_runtime_py.",
            ],
            commands=[
                "ros2 interface show " + diagnosis.msg_type,
                "source /opt/ros/$ROS_DISTRO/setup.bash",
            ],
        )

    def _publisher_health(self, diagnosis: TopicDiagnosis) -> None:
        if diagnosis.pub_count <= 0:
            return
        if diagnosis.sample_duration_sec > 0 and diagnosis.message_count == 0:
            observer_note = ""
            if diagnosis.observation_qos == "sensor_data_fallback":
                observer_note = (
                    " The observer used the sensor-data fallback because endpoint QoS "
                    "was unavailable; this zero-message result is not conclusive."
                )
            self._add(
                diagnosis,
                code="publisher_no_messages",
                severity=TopicStatus.ERROR,
                problem="Publisher exists but no messages arrived",
                detail=(
                    f"Observed {diagnosis.sample_duration_sec:.1f}s with "
                    f"{diagnosis.pub_count} publisher(s) and zero messages."
                    f"{observer_note}"
                ),
                causes=[
                    "QoS incompatibility prevents delivery to the observer.",
                    "The driver or publisher callback is stalled.",
                    "The publisher process crashed after graph discovery.",
                ],
                commands=[
                    f"ros2 topic echo --qos-durability volatile {diagnosis.topic_name}",
                    f"ros2 topic info -v {diagnosis.topic_name}",
                    "roscope graph",
                ],
                evidence={
                    "publishers": diagnosis.pub_count,
                    "sample_duration_sec": diagnosis.sample_duration_sec,
                    "message_count": diagnosis.message_count,
                    "observation_qos": diagnosis.observation_qos,
                },
            )

    def _freshness(self, diagnosis: TopicDiagnosis) -> None:
        if diagnosis.stale_timeout_ms <= 0:
            return
        if diagnosis.last_message_age_ms <= diagnosis.stale_timeout_ms:
            return
        if (
            not diagnosis.last_message_seen
            and diagnosis.message_count == 0
            and diagnosis.rate <= 0
        ):
            return
        self._add(
            diagnosis,
            code="stale_messages",
            severity=TopicStatus.ERROR,
            problem="Messages are stale",
            detail=(
                f"The last observed message is {diagnosis.last_message_age_ms:.0f}ms old; "
                f"threshold is {diagnosis.stale_timeout_ms:.0f}ms."
            ),
            causes=[
                "The upstream driver has stopped producing data.",
                "The executor or CPU is overloaded.",
                "The network or DDS middleware is dropping traffic.",
            ],
            commands=[
                f"ros2 topic hz {diagnosis.topic_name}",
                f"ros2 topic echo --once {diagnosis.topic_name}",
                f"ros2 topic info -v {diagnosis.topic_name}",
            ],
            evidence={
                "last_message_age_ms": diagnosis.last_message_age_ms,
                "stale_timeout_ms": diagnosis.stale_timeout_ms,
            },
        )

    def _frequency(self, diagnosis: TopicDiagnosis) -> None:
        if diagnosis.expected_rate <= 0 or diagnosis.rate <= 0:
            return
        threshold = diagnosis.expected_rate * self.rate_warn_threshold
        if diagnosis.rate >= threshold:
            return
        self._add(
            diagnosis,
            code="frequency_degraded",
            severity=TopicStatus.WARN,
            problem="Message frequency is degraded",
            detail=(
                f"Observed {diagnosis.rate:.2f}Hz; expected at least "
                f"{threshold:.2f}Hz ({self.rate_warn_threshold:.0%} of "
                f"{diagnosis.expected_rate:.2f}Hz)."
            ),
            causes=[
                "The publisher callback or sensor driver is overloaded.",
                "Executor scheduling or CPU contention is delaying callbacks.",
                "DDS transport is losing or retransmitting samples.",
            ],
            commands=[
                f"ros2 topic hz {diagnosis.topic_name}",
                f"ros2 topic info -v {diagnosis.topic_name}",
            ],
            evidence={
                "observed_rate_hz": diagnosis.rate,
                "expected_rate_hz": diagnosis.expected_rate,
            },
        )

    def _subscriber_health(self, diagnosis: TopicDiagnosis) -> None:
        if diagnosis.pub_count > 0 and diagnosis.sub_count == 0:
            self._add(
                diagnosis,
                code="no_subscribers",
                severity=TopicStatus.WARN,
                problem="Publisher has no subscribers",
                detail="Data is being produced but no consumer is currently connected.",
                causes=[
                    "The consumer node has not started.",
                    "The consumer uses a different topic name or namespace.",
                    "The consumer's QoS request is incompatible with the publisher.",
                ],
                commands=[
                    "roscope graph",
                    f"ros2 topic info -v {diagnosis.topic_name}",
                ],
                evidence={"publishers": diagnosis.pub_count, "subscribers": 0},
            )

    def _qos(self, diagnosis: TopicDiagnosis) -> None:
        issues = list(dict.fromkeys(diagnosis.qos_issues + diagnosis.qos_profile_missing))
        if not issues:
            return
        incompatible = any("incompat" in issue.lower() for issue in issues)
        severity = TopicStatus.ERROR if incompatible else TopicStatus.WARN
        self._add(
            diagnosis,
            code="qos_incompatible" if incompatible else "qos_mismatch",
            severity=severity,
            problem="QoS may prevent communication" if incompatible else "QoS profiles differ",
            detail=" ".join(issues),
            causes=[
                "The subscriber requests reliability or durability the publisher does not offer.",
                "The endpoints were configured with different QoS presets.",
                "A sensor-data profile is being mixed with a services/default profile.",
            ],
            commands=[
                f"ros2 topic info -v {diagnosis.topic_name}",
                f"ros2 topic echo --qos-reliability best_effort {diagnosis.topic_name}",
            ],
            evidence={"issues": issues},
        )

    def _type_consistency(self, diagnosis: TopicDiagnosis) -> None:
        endpoint_types = {
            endpoint.topic_type
            for endpoint in [*diagnosis.publishers, *diagnosis.subscribers]
            if endpoint.topic_type and endpoint.topic_type != "N/A"
        }
        if len(endpoint_types) <= 1:
            return
        self._add(
            diagnosis,
            code="type_mismatch",
            severity=TopicStatus.ERROR,
            problem="Publisher and subscriber types do not match",
            detail="Endpoint types: " + ", ".join(sorted(endpoint_types)),
            causes=[
                "Nodes were built against different interface definitions.",
                "A remapped topic is connecting unrelated message types.",
            ],
            commands=[
                f"ros2 topic info -v {diagnosis.topic_name}",
                "ros2 interface list",
            ],
            evidence={"endpoint_types": sorted(endpoint_types)},
        )

    @staticmethod
    def _add(
        diagnosis: TopicDiagnosis,
        *,
        code: str,
        severity: TopicStatus,
        problem: str,
        detail: str = "",
        causes: list[str] | None = None,
        commands: list[str] | None = None,
        evidence: dict | None = None,
    ) -> None:
        diagnosis.add_finding(
            Finding(
                code=code,
                severity=severity,
                problem=problem,
                detail=detail,
                possible_causes=causes or [],
                suggested_commands=commands or [],
                evidence=evidence or {},
            )
        )
