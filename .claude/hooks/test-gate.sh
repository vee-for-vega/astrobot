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

if ! $PYTEST -q tests/ > /tmp/astrobot_pytest_out.txt 2>&1; then
  echo "Task blocked: locked Python tests are failing. Fix the implementation" >&2
  echo "to satisfy the existing tests. Do NOT edit the tests to pass." >&2
  echo "" >&2
  tail -n 20 /tmp/astrobot_pytest_out.txt >&2
  exit 2
fi

# Web suite (vitest). Runs only where the web env is installed so a
# backend-only machine is not blocked on node_modules.
if [ -d web/node_modules ] && grep -q '"test"' web/package.json 2>/dev/null; then
  if ! (cd web && npm test --silent) > /tmp/astrobot_vitest_out.txt 2>&1; then
    echo "Task blocked: locked web tests (vitest) are failing. Fix the" >&2
    echo "implementation to satisfy the existing tests. Do NOT edit them." >&2
    echo "" >&2
    tail -n 20 /tmp/astrobot_vitest_out.txt >&2
    exit 2
  fi
fi

exit 0
