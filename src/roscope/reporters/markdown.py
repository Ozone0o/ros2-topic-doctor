"""Markdown report suitable for CI artifacts and issue attachments."""

from __future__ import annotations

from roscope.core.models import ScanReport


def format_markdown_report(report: ScanReport) -> str:
    summary = report.summary
    lines = [
        "# Roscope communication report",
        "",
        f"**Status:** `{report.status.name}`",
        f"**Topics:** {summary['topics']}",
        f"**OK:** {summary['ok']} · **WARN:** {summary['warn']} · **ERROR:** {summary['error']}",
        "",
        "| Status | Topic | Type | Rate | Pub/Sub | Finding |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for topic in report.topics:
        finding = topic.findings[0].problem if topic.findings else "Healthy"
        lines.append(
            f"| {topic.status.name} | `{topic.topic_name}` | `{topic.msg_type}` | "
            f"{topic.rate:.2f} Hz | {topic.pub_count}/{topic.sub_count} | {finding} |"
        )
    lines.append("")
    for topic in report.topics:
        if not topic.findings:
            continue
        lines.extend([f"## `{topic.topic_name}` — {topic.status.name}", ""])
        for finding in topic.findings:
            lines.append(f"### {finding.problem} (`{finding.code}`)")
            if finding.detail:
                lines.extend(["", finding.detail])
            if finding.possible_causes:
                lines.extend(["", "Possible causes:"])
                lines.extend(f"- {cause}" for cause in finding.possible_causes)
            if finding.suggested_commands:
                lines.extend(["", "Suggested commands:"])
                lines.extend(f"- `{command}`" for command in finding.suggested_commands)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
