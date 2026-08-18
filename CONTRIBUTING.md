# Contributing to Roscope

Thanks for helping improve Roscope. Keep changes focused on reliable ROS 2
communication diagnostics and include the smallest reproducible test for every
behavior change.

## Development

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/pytest -q
.venv/bin/ruff check src tests examples
```

CI covers Python 3.10 through 3.13. ROS graph commands require a sourced ROS 2
environment; the offline test suite and `roscope --help` must remain usable
without ROS installed. Do not run diagnostic commands against production
robots from an unreviewed pull request.

Before opening a pull request, update the README or `CHANGELOG.md` when the
user-facing command or output contract changes. Do not commit caches, wheels,
`__pycache__` directories, or local ROS build output.

Pull requests should explain the failure mode being changed, include tests,
and keep the public package name and `roscope` entry point canonical.
