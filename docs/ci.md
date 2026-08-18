# CI and deployment checks

Roscope is designed to run after a ROS 2 launch test, in a hardware-in-the-loop
job, or as a pre-deployment smoke check.

```bash
source /opt/ros/$ROS_DISTRO/setup.bash
roscope scan --duration 2 --json --fail-on error > ros-health.json
```

Use `--fail-on warn` when every degraded topic should block the pipeline. Use
`--fail-on error` when warnings are expected during startup and only hard
communication failures should fail the job.

`watch --json` emits JSON Lines. It can be piped to a log collector without
waiting for a complete report:

```bash
roscope watch /scan --interval 1 --json --iterations 60 \
  | tee scan-health.jsonl
```

The process exit status is `0` for healthy, `1` for warnings, `2` for errors,
`3` for a startup/collection error, and `130` when interrupted.
