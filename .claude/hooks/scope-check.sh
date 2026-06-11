#!/bin/bash
# scope-check.sh — non-blocking nudge on TaskCreated.
# If the new task description looks like an implementation task (contains
# "implement", "build the", "add the", "write the") but does NOT mention
# tests, criteria, or a locked-tests dependency, print a reminder.
# Exit 0 always — this is advisory, not blocking.

INPUT=$(cat)
DESC=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('description',''))" 2>/dev/null || echo "")

IMPL_PATTERN="implement|build the|add the|write the"
TEST_PATTERN="test|criteria|locked|spec|LOCKED"

if echo "$DESC" | grep -qiE "$IMPL_PATTERN"; then
  if ! echo "$DESC" | grep -qiE "$TEST_PATTERN"; then
    echo "SCOPE CHECK: task looks like an implementation task but mentions no tests or locked criteria." >&2
    echo "  Per CLAUDE.md: every implementation task must depend on a locked-tests task." >&2
    echo "  If the locked-tests task already exists, reference it in this task's description." >&2
  fi
fi

exit 0
