# Roscope architecture

Roscope uses a fact → analysis → report pipeline:

```text
ROS 2 graph / DDS
       │
       ▼
collectors ──► core models ──► analyzers ──► reporters
                                      │
                                      ├─ terminal
                                      ├─ JSON / JSONL
                                      └─ Markdown
```

## Boundaries

- `core.models` contains the versioned result shape. It has no ROS imports.
- `collectors` owns graph discovery, endpoint QoS extraction, and bounded
  message sampling. The default `RosCollector` is lazy about `rclpy`.
- `core.engine` and `analyzers` only interpret observations. A collector never
  decides that a topic is healthy.
- `reporters` render the same model for people and automation. They do not
  collect data or alter exit status.
- `plugins` provides small in-process contracts for future node health, service,
  action, bag, or DDS collectors and analyzers.

## Finding contract

Every issue has a stable `code`, severity, human explanation, evidence,
possible causes, and suggested commands. Examples include:

- `topic_missing`
- `publisher_no_messages`
- `subscriber_waiting`
- `qos_incompatible`
- `frequency_degraded`
- `stale_messages`

The JSON output keeps stable flat fields and adds the structured `findings` list.
New fields should be additive and the
`schema_version` must be updated when a breaking change is unavoidable.
