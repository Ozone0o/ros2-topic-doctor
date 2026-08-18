#!/usr/bin/env bash
set -euo pipefail

# Run after sourcing ROS 2 and starting the robot stack. JSON is retained as a
# CI artifact while --fail-on error lets non-critical warnings be triaged
# without blocking deployment.
roscope scan --duration 2 --json --fail-on error > ros-health.json
echo "Roscope preflight passed; report saved to ros-health.json"
