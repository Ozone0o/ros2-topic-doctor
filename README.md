# Roscope

> **Understand why your ROS 2 system is unhealthy.**

Roscope is a modern ROS 2 observability and diagnostic toolkit. It helps robotics developers diagnose communication failures before deployment—fast enough for an interactive terminal, structured enough for CI and incident reports.

It is the communication-layer companion to `htop` and Wireshark: start with a symptom, see the evidence, and get the next command to run.

## Terminal demo

```console
$ roscope inspect /camera/image_raw --expected-rate 30

Roscope inspect /camera/image_raw
────────────────────────────────────────────────────────────────
Type          sensor_msgs/msg/Image
Publishers    1
Subscribers   2
Rate          0.00 Hz
Last message  never observed
Status        ERROR  (exit 2)

Problem:
  ✖ Publisher exists but no messages arrived [publisher_no_messages]
    Observed 3.0s with 1 publisher(s) and zero messages.

Possible causes:
  1. QoS incompatibility prevents delivery to the observer.
  2. The driver or publisher callback is stalled.
  3. The publisher process crashed after graph discovery.

Suggested commands:
  $ ros2 topic echo --qos-durability volatile /camera/image_raw
  $ ros2 topic info -v /camera/image_raw
    $ roscope graph
```

Use Roscope when a camera stream appears in the graph but perception sees
nothing, a lidar rate drops under load, a subscriber is waiting forever, or a
launch/pre-deployment check needs evidence instead of a binary “topic exists”
answer.

## Quick start

Roscope is a Python CLI. ROS 2 supplies `rclpy` and interface packages; install Roscope into the same environment after sourcing your ROS distribution.

```bash
source /opt/ros/$ROS_DISTRO/setup.bash
# Published releases: python3 -m pip install roscope
# From this checkout:
python3 -m pip install .

roscope inspect /camera/image_raw
roscope scan
roscope graph
```

For a ROS 2 workspace:

```bash
colcon build --packages-select roscope
source install/setup.bash
roscope inspect /scan
```

## Core capabilities

- **Explain failures, not just metadata** — missing topics, stalled publishers, waiting subscribers, QoS incompatibility, stale messages, and degraded frequency become prioritized findings.
- **CLI-first workflow** — `inspect`, `scan`, `watch`, `graph`, and `report` compose naturally with the existing ROS 2 command-line tools.
- **Automation-ready** — deterministic JSON, JSON Lines for watch mode, meaningful exit codes, and `--fail-on error` for CI gates.
- **Low-friction observation** — no daemon and no GUI required; a short-lived ROS node samples the live graph and exits.
- **Small extension seam** — collectors and analyzers are separated internally; the plugin module is not yet a stable discovery API.

## Commands

### Inspect one communication path

```bash
roscope inspect /camera/image_raw
roscope inspect /scan --duration 5 --expected-rate 10 --stale-timeout 3000
roscope inspect /joint_states --json
```

`inspect` reports endpoint counts, message type, observed rate, freshness, QoS, and an explanation of every detected problem. A topic can be present in the ROS graph while still being unhealthy; Roscope samples it to distinguish discovery from actual data flow.

### Scan the graph

```bash
roscope scan
roscope scan --pattern camera --duration 1
roscope scan --json > ros-health.json
```

`scan` ranks every discovered topic using the same diagnostic engine. Use `--pattern` to focus a large robot or `--include-hidden` when investigating parameter/event infrastructure. Eligible topics are sampled in one shared observation window, so scan time is approximately the requested duration rather than the duration multiplied by topic count. The JSON result records whether the observer used a fallback QoS profile or profiles discovered from publisher endpoints.

### Watch a topic

```bash
roscope watch /scan --interval 2
roscope watch /camera/image_raw --interval 1 --once --json
```

Human output is readable between observations. `--json` emits one JSON object per line, so a deployment monitor can stream it without parsing terminal decoration.

### Understand the graph

```bash
roscope graph
roscope graph --json | jq '.topics[] | select(.publishers == 0)'
```

The graph view shows discovered nodes, topic types, and publisher/subscriber counts. It is deliberately compact and terminal-friendly rather than a GUI graph editor.

### Create a report

```bash
roscope report --format markdown --output ros-health.md
roscope report --format json --output ros-health.json
```

Markdown reports are suitable for CI artifacts, bug reports, and field handoffs. The JSON schema is versioned and additive so scripts can safely consume it.

### Package naming

The package and executable are both `roscope`. Tests, examples, ROS metadata,
and automation are released under this one canonical name.

## CI and exit codes

Every health command returns a useful process status:

| Code | Meaning |
| ---: | --- |
| `0` | Healthy, or below the selected failure threshold |
| `1` | Warning detected (frequency degradation, no subscribers, QoS warning) |
| `2` | Error detected (missing topic, stalled publisher, stale data, incompatible QoS) |
| `3` | Roscope could not start or collect data |
| `130` | Interrupted with Ctrl-C |

Fail a pipeline only when a real error is present:

```bash
roscope scan --duration 2 --json --fail-on error > ros-health.json
test $? -eq 0
```

Or gate a launch/preflight check on every warning:

```bash
roscope inspect /tf --expected-rate 30 --fail-on warn
```

## How diagnosis works

Roscope separates observation from interpretation:

1. The ROS collector reads graph endpoints, message type, and QoS profiles.
2. A bounded sampler measures delivered messages and receive-time freshness.
3. The diagnostic engine correlates those signals and emits stable finding codes.
4. Reporters render the same result as terminal text, JSON, JSON Lines, or Markdown.

For example, a discovered publisher with zero delivered messages is reported as `publisher_no_messages`, with likely causes such as QoS incompatibility, a stalled driver, or a crashed process. The output includes commands that narrow those hypotheses.

## Architecture

```text
roscope/
├── core/        domain models, diagnostic engine, use-case orchestration
├── collectors/  ROS 2 graph/message observation backends
├── analyzers/   topic health rules and future node/service/action analyzers
├── reporters/   terminal, JSON/JSONL, and Markdown output
├── cli/         product CLI and command dispatch
└── plugins/     internal extension contracts (not yet a stable plugin API)
```

The built-in collector is intentionally the only layer that imports ROS 2. The core and reporters run in a plain Python environment, which keeps unit tests and automation tooling portable.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest -q
ruff check src tests
```

The rule engine and reporters do not require a running ROS graph. A deterministic example is available at [`examples/demo.py`](examples/demo.py), and the CI workflow runs those checks on supported Python versions.

## ROS 2 integration notes

- `rclpy` and `rosidl_runtime_py` should come from the ROS 2 distribution rather than a generic PyPI environment.
- Sampling selects a least-demanding observer profile from discovered publisher endpoints when possible and records the endpoint count. If discovery does not expose one, the result records `sensor_data_fallback`; treat a zero-message result in that case as inconclusive and confirm with `ros2 topic info -v`.
- Freshness is measured at receipt time. This works for messages without a standard `Header` and avoids confusing a stale source timestamp with a live DDS connection.

## Roadmap

The CLI and diagnostic contracts are ready for additional collectors and analyzers. Planned extensions include node lifecycle/heartbeat health, service and action availability, rosbag replay checks, and DDS vendor-level discovery and transport evidence. The product remains CLI-first and automation-friendly; a GUI is not a dependency of the core workflow.

## License

MIT. See [`LICENSE`](LICENSE).
