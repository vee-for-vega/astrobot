#!/bin/bash
# TaskCompleted hook: the objective gate.
# An agent cannot mark a task complete unless the LOCKED tests pass.
# Exit 2 is the ONLY exit code that blocks in Claude Code — exit 1 is treated
# as a non-blocking error and would let the task complete anyway. So we are
# deliberate: pass -> exit 0, fail -> exit 2.

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

# System python3 on this machine is 3.9 and cannot import the codebase
# (PEP 604 unions). Always prefer the project venv.
PYTEST="python3 -m pytest"
if [ -x .venv/bin/python ]; then
  PYTEST=".venv/bin/python -m pytest"
fi

if $PYTEST -q tests/ > /tmp/astrobot_pytest_out.txt 2>&1; then
  exit 0
else
  echo "Task blocked: locked tests are failing. Fix the implementation to" >&2
  echo "satisfy the existing tests. Do NOT edit the tests to pass." >&2
  echo "" >&2
  tail -n 20 /tmp/astrobot_pytest_out.txt >&2
  exit 2
fi
