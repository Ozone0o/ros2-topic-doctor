"""Readable, CI-friendly terminal output."""

from __future__ import annotations

import os

from roscope.core.models import GraphSnapshot, ScanReport, TopicDiagnosis, TopicStatus


def format_diagnosis_text(
    diagnosis: TopicDiagnosis,
    *,
    color: bool | None = None,
) -> str:
    use_color = _should_color(color)
    status = _status(diagnosis.status, use_color)
    lines = [
        f"Roscope inspect {diagnosis.topic_name}",
        "─" * max(40, len(diagnosis.topic_name) + 17),
        f"Type          {diagnosis.msg_type}",
        f"Publishers    {diagnosis.pub_count}",
        f"Subscribers   {diagnosis.sub_count}",
        f"Rate          {_rate(diagnosis.rate)}",
        f"Last message  {_last_message(diagnosis)}",
        f"Status        {status}  (exit {diagnosis.exit_code})",
    ]

    if diagnosis.qos_pub.reliability != "UNKNOWN" or diagnosis.pub_count:
        lines.extend(_qos_lines("Publisher QoS", diagnosis.qos_pub))
    if diagnosis.sub_count:
        lines.extend(_qos_lines("Subscriber QoS", diagnosis.qos_sub))

    if diagnosis.findings:
        lines.extend(["", "Problem:"])
        for finding in diagnosis.findings:
            marker = "✖" if finding.severity == TopicStatus.ERROR else "⚠"
            lines.append(f"  {marker} {finding.problem} [{finding.code}]")
            if finding.detail:
                lines.append(f"    {finding.detail}")
    else:
        lines.extend(["", "Problem: none detected"])

    causes = diagnosis.possible_causes
    if causes:
        lines.extend(["", "Possible causes:"])
        lines.extend(f"  {index}. {cause}" for index, cause in enumerate(causes, 1))

    commands = diagnosis.suggested_commands
    if commands:
        lines.extend(["", "Suggested commands:"])
        lines.extend(f"  $ {command}" for command in commands)
    return "\n".join(lines)


def format_scan_text(report: ScanReport, *, color: bool | None = None) -> str:
    use_color = _should_color(color)
    lines = ["Roscope scan", "─" * 72]
    if not report.topics:
        lines.append("No topics discovered.")
    else:
        lines.append(f"{'STATUS':<8} {'TOPIC':<34} {'RATE':>10} {'PUB/SUB':>8} PROBLEMS")
        for topic in report.topics:
            problem = topic.findings[0].problem if topic.findings else "healthy"
            status = _status(topic.status, use_color)
            rate = _rate(topic.rate)
            endpoint_count = f"{topic.pub_count}/{topic.sub_count}"
            lines.append(
                f"{status:<8} {topic.topic_name[:34]:<34} {rate:>10} {endpoint_count:>8} {problem}"
            )
    summary = report.summary
    lines.extend(
        [
            "",
            (
                f"Summary: {summary['topics']} topics · "
                f"{summary['ok']} OK · {summary['warn']} WARN · {summary['error']} ERROR"
            ),
            f"Exit: {report.exit_code}",
        ]
    )
    return "\n".join(lines)


def format_graph_text(graph: GraphSnapshot) -> str:
    lines = ["Roscope graph", "─" * 72]
    lines.append(f"Nodes: {len(graph.nodes)}  Topics: {len(graph.topics)}")
    if graph.nodes:
        lines.extend(["", "Nodes:"])
        lines.extend(
            f"  • {node.get('node', node.get('name', 'unknown'))}" for node in graph.nodes
        )
    if graph.topics:
        lines.extend(["", "Topics:"])
        for topic in graph.topics:
            lines.append(
                f"  • {topic.get('name', '')}  "
                f"{topic.get('type', 'N/A')}  "
                f"({topic.get('publishers', 0)} pub / {topic.get('subscribers', 0)} sub)"
            )
    return "\n".join(lines)


def _qos_lines(title: str, qos) -> list[str]:
    return [
        "",
        title + ":",
        f"  reliability={qos.reliability} durability={qos.durability} "
        f"history={qos.history} depth={qos.depth}",
    ]


def _rate(rate: float) -> str:
    return f"{rate:.2f} Hz" if rate > 0 else "no samples"


def _last_message(diagnosis: TopicDiagnosis) -> str:
    if not diagnosis.last_message_seen:
        return "never observed"
    return f"{diagnosis.last_message_age_ms:.0f} ms ago"


def _status(status: TopicStatus, color: bool) -> str:
    label = status.name
    if not color:
        return label
    codes = {
        TopicStatus.OK: "\033[32m",
        TopicStatus.WARN: "\033[33m",
        TopicStatus.ERROR: "\033[31m",
    }
    return f"{codes.get(status, '')}{label}\033[0m"


def _should_color(color: bool | None) -> bool:
    if color is not None:
        return color
    return bool(os.environ.get("TERM")) and "NO_COLOR" not in os.environ
