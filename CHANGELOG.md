# Changelog

## 0.2.0 — Roscope

- Repositioned the project as a ROS 2 observability and diagnostic toolkit.
- Added the unified `roscope inspect`, `scan`, `watch`, `graph`, and `report` CLI.
- Added structured findings with causes, evidence, suggested commands, JSON/JSONL,
  Markdown reports, and CI exit thresholds.
- Split the code into core, collectors, analyzers, reporters, CLI, and plugin
  contracts.
- Consolidated the package, executable, ROS metadata, tests, and examples under
  the single `roscope` name.
