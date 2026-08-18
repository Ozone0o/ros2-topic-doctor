"""The ``roscope`` CLI.

Argument parsing stays here; ROS imports remain inside ``RosRuntime`` so
``roscope --help`` and ``roscope --version`` work everywhere.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from roscope import __version__
from roscope.collectors.ros import RosCollector, RosRuntime, RosUnavailableError
from roscope.core.models import TopicStatus
from roscope.core.service import RoscopeService
from roscope.reporters.json import (
    format_diagnosis_json,
    format_graph_json,
    format_json_line,
    format_scan_json,
)
from roscope.reporters.markdown import format_markdown_report
from roscope.reporters.terminal import (
    format_diagnosis_text,
    format_graph_text,
    format_scan_text,
)

RUNTIME_ERROR_EXIT_CODE = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="roscope",
        description=(
            "Understand why your ROS 2 system is unhealthy. "
            "Inspect communication health before deployment."
        ),
        epilog=("Examples: roscope inspect /camera/image_raw | roscope scan | roscope graph"),
    )
    parser.add_argument("--version", action="version", version=f"Roscope {__version__}")
    parser.add_argument(
        "--json",
        dest="global_json",
        action="store_true",
        help="emit machine-readable JSON (can also be placed after a command)",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="diagnose one topic and explain likely communication failures",
    )
    inspect_parser.add_argument("topic", help="topic name, for example /camera/image_raw")
    _add_observation_options(inspect_parser, duration=3.0)

    scan_parser = subparsers.add_parser(
        "scan",
        help="scan the ROS graph and rank unhealthy topics",
    )
    _add_observation_options(scan_parser, duration=0.5)
    scan_parser.add_argument("--pattern", help="only inspect topic names containing TEXT")
    scan_parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="include ROS hidden topics such as parameter event topics",
    )

    watch_parser = subparsers.add_parser(
        "watch",
        help="continuously observe a topic and emit one result per interval",
    )
    watch_parser.add_argument("topic", help="topic name to watch")
    watch_parser.add_argument(
        "--interval",
        type=_positive_float,
        default=2.0,
        help="observation interval in seconds (default: 2)",
    )
    watch_parser.add_argument(
        "--iterations",
        type=_non_negative_int,
        default=0,
        help="number of observations; 0 means run until Ctrl-C",
    )
    watch_parser.add_argument(
        "--once",
        dest="iterations",
        action="store_const",
        const=1,
        help="observe once and exit",
    )
    _add_health_options(watch_parser)

    graph_parser = subparsers.add_parser(
        "graph",
        help="show nodes, topics, and endpoint counts discovered in the ROS graph",
    )
    graph_parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="include hidden topics",
    )
    _add_output_options(graph_parser)

    report_parser = subparsers.add_parser(
        "report",
        help="create a shareable Markdown or JSON communication health report",
    )
    _add_observation_options(report_parser, duration=0.5)
    report_parser.add_argument("--pattern", help="only inspect topic names containing TEXT")
    report_parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="include hidden topics",
    )
    report_parser.add_argument(
        "--format",
        choices=("terminal", "markdown", "json"),
        default="terminal",
        help="report format (default: terminal)",
    )
    report_parser.add_argument(
        "--output",
        type=Path,
        help="write the report to FILE instead of stdout",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run Roscope and return a CI-friendly exit code."""

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    try:
        with RosRuntime(node_name=args.node_name) as runtime:
            service = RoscopeService(RosCollector(runtime))
            return _dispatch(service, args)
    except RosUnavailableError as exc:
        return _runtime_error(args, str(exc))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        return _runtime_error(args, f"{type(exc).__name__}: {exc}")


def _dispatch(service: RoscopeService, args: argparse.Namespace) -> int:
    as_json = bool(getattr(args, "global_json", False) or getattr(args, "as_json", False))
    color = not bool(getattr(args, "no_color", False)) and not as_json
    fail_on = getattr(args, "fail_on", "warn")

    if args.command == "inspect":
        diagnosis = service.inspect_topic(
            args.topic,
            duration_sec=args.duration,
            expected_rate=args.expected_rate,
            stale_timeout_ms=args.stale_timeout,
        )
        output = (
            format_diagnosis_json(diagnosis)
            if as_json
            else format_diagnosis_text(diagnosis, color=color)
        )
        print(output)
        return _exit_for_status(diagnosis.status, fail_on)

    if args.command == "scan":
        report = service.scan(
            duration_sec=args.duration,
            expected_rate=args.expected_rate,
            stale_timeout_ms=args.stale_timeout,
            include_hidden=args.include_hidden,
            pattern=args.pattern,
        )
        print(format_scan_json(report) if as_json else format_scan_text(report, color=color))
        return _exit_for_status(report.status, fail_on)

    if args.command == "watch":
        return _watch(service, args, as_json=as_json, color=color, fail_on=fail_on)

    if args.command == "graph":
        graph = service.graph(include_hidden=args.include_hidden)
        print(format_graph_json(graph) if as_json else format_graph_text(graph))
        return 0

    if args.command == "report":
        report = service.scan(
            duration_sec=args.duration,
            expected_rate=args.expected_rate,
            stale_timeout_ms=args.stale_timeout,
            include_hidden=args.include_hidden,
            pattern=args.pattern,
        )
        if as_json or args.format == "json":
            output = format_scan_json(report)
        elif args.format == "markdown":
            output = format_markdown_report(report)
        else:
            output = format_scan_text(report, color=color)
        _write_or_print(output, args.output)
        return _exit_for_status(report.status, fail_on)

    raise AssertionError(f"unknown command: {args.command}")


def _watch(
    service: RoscopeService,
    args: argparse.Namespace,
    *,
    as_json: bool,
    color: bool,
    fail_on: str,
) -> int:
    worst_status = TopicStatus.OK
    iteration = 0
    while args.iterations == 0 or iteration < args.iterations:
        diagnosis = service.inspect_topic(
            args.topic,
            duration_sec=args.interval,
            expected_rate=args.expected_rate,
            stale_timeout_ms=args.stale_timeout,
        )
        if as_json:
            print(format_json_line(diagnosis), flush=True)
        else:
            if iteration:
                print("\n" + "=" * 72)
            print(format_diagnosis_text(diagnosis, color=color), flush=True)
        worst_status = max(worst_status, diagnosis.status)
        iteration += 1
        if diagnosis.sample_duration_sec <= 0 and (
            args.iterations == 0 or iteration < args.iterations
        ):
            time.sleep(args.interval)
    return _exit_for_status(worst_status, fail_on)


def _add_observation_options(parser: argparse.ArgumentParser, *, duration: float) -> None:
    parser.add_argument(
        "--duration",
        type=_positive_float,
        default=duration,
        help=f"observation window in seconds (default: {duration:g})",
    )
    _add_health_options(parser)


def _add_health_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--expected-rate",
        type=_positive_float,
        default=0.0,
        help="expected message frequency in Hz; enables degradation detection",
    )
    parser.add_argument(
        "--stale-timeout",
        type=_positive_float,
        default=5000.0,
        metavar="MILLISECONDS",
        help="maximum allowed message age (default: 5000)",
    )
    _add_output_options(parser)


def _add_output_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="emit machine-readable JSON",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="disable ANSI status colors",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="enable additional collector diagnostics where available",
    )
    parser.add_argument(
        "--fail-on",
        choices=("warn", "error"),
        default="warn",
        help="CI threshold: fail on WARN (default) or only ERROR",
    )
    parser.add_argument(
        "--node-name",
        default="roscope",
        help="temporary ROS node name (default: roscope)",
    )


def _write_or_print(output: str, path: Path | None) -> None:
    if path is None:
        print(output, end="" if output.endswith("\n") else "\n")
        return
    path.write_text(output + ("" if output.endswith("\n") else "\n"), encoding="utf-8")
    print(f"Wrote {path}")


def _runtime_error(args: argparse.Namespace, message: str) -> int:
    as_json = bool(getattr(args, "global_json", False) or getattr(args, "as_json", False))
    if as_json:
        print(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "status": "ERROR",
                    "exit_code": RUNTIME_ERROR_EXIT_CODE,
                    "error": message,
                },
                ensure_ascii=False,
            )
        )
    else:
        print(f"roscope: {message}", file=sys.stderr)
    return RUNTIME_ERROR_EXIT_CODE


def _exit_for_status(status: TopicStatus, fail_on: str) -> int:
    threshold = TopicStatus.WARN if fail_on == "warn" else TopicStatus.ERROR
    return int(status) if status >= threshold else 0


def _positive_float(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def _non_negative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return number
