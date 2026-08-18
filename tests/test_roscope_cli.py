"""CLI contract tests that deliberately run without ROS 2 installed."""

import json

from roscope.cli import app
from roscope.core.models import TopicStatus


def test_parser_exposes_product_commands() -> None:
    parser = app.build_parser()
    help_text = parser.format_help()

    for command in ("inspect", "scan", "watch", "graph", "report"):
        assert command in help_text


def test_json_runtime_error_is_machine_readable(monkeypatch, capsys) -> None:
    class MissingRuntime:
        def __init__(self, **_kwargs) -> None:
            pass

        def __enter__(self):
            raise app.RosUnavailableError("ROS is not sourced")

        def __exit__(self, *_args) -> None:
            return None

    monkeypatch.setattr(app, "RosRuntime", MissingRuntime)
    exit_code = app.main(["inspect", "/scan", "--json"])

    assert exit_code == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ERROR"
    assert payload["exit_code"] == 3


def test_fail_on_threshold() -> None:
    assert app._exit_for_status(TopicStatus.WARN, "warn") == 1
    assert app._exit_for_status(TopicStatus.WARN, "error") == 0
    assert app._exit_for_status(TopicStatus.ERROR, "error") == 2
