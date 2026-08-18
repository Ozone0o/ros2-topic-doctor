"""Tests for human and machine Roscope reports."""

import json

from roscope.core.engine import DiagnosticEngine
from roscope.core.models import GraphSnapshot, ScanReport, TopicDiagnosis
from roscope.reporters.json import format_diagnosis_json, format_graph_json, format_scan_json
from roscope.reporters.markdown import format_markdown_report
from roscope.reporters.terminal import format_diagnosis_text, format_graph_text, format_scan_text


def _broken_topic() -> TopicDiagnosis:
    diagnosis = TopicDiagnosis(
        topic_name="/camera/image_raw",
        msg_type="sensor_msgs/msg/Image",
        topic_exists=True,
        pub_count=1,
        sub_count=1,
        sample_duration_sec=2.0,
    )
    return DiagnosticEngine().analyze(diagnosis)


def test_terminal_report_explains_problem_and_next_steps() -> None:
    text = format_diagnosis_text(_broken_topic(), color=False)

    assert "Problem:" in text
    assert "Possible causes:" in text
    assert "Suggested commands:" in text
    assert "publisher_no_messages" in text


def test_json_report_is_parseable_and_structured() -> None:
    data = json.loads(format_diagnosis_json(_broken_topic()))

    assert data["schema_version"] == "1.0"
    assert data["findings"][0]["code"] == "publisher_no_messages"
    assert data["exit_code"] == 2


def test_scan_and_markdown_reports_share_the_same_status() -> None:
    report = ScanReport(topics=[_broken_topic()])

    assert json.loads(format_scan_json(report))["status"] == "ERROR"
    assert "ERROR" in format_scan_text(report, color=False)
    markdown = format_markdown_report(report)
    assert "# Roscope communication report" in markdown
    assert "publisher_no_messages" in markdown


def test_graph_reporters() -> None:
    graph = GraphSnapshot(
        nodes=[{"node": "/robot/camera"}],
        topics=[
            {
                "name": "/camera/image_raw",
                "type": "sensor_msgs/msg/Image",
                "publishers": 1,
                "subscribers": 2,
            }
        ],
    )

    assert "/robot/camera" in format_graph_text(graph)
    assert json.loads(format_graph_json(graph))["summary"]["topics"] == 1
