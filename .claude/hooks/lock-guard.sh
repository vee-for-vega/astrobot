#!/bin/bash
# PostToolUse hook (Edit|Write): guard locked tests.
# If an agent edits a test file that carries the LOCKED marker, surface a
# warning to the conversation. Tests bearing "# LOCKED" in their header are
# frozen acceptance criteria and must only change via an architect task.
#
# PostToolUse cannot un-edit the file (the write already happened), but it
# feeds the warning back to the agent so it self-corrects, and leaves an
# audit trail.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null)

case "$FILE_PATH" in
  *tests/*)
    if grep -q "# LOCKED" "$FILE_PATH" 2>/dev/null; then
      echo "WARNING: $FILE_PATH is a LOCKED test file." >&2
      echo "Locked tests encode architect-approved acceptance criteria and may" >&2
      echo "not be modified to make an implementation pass. If a criterion must" >&2
      echo "change, raise it as a new architect task. Revert this edit." >&2
    fi
    ;;
esac

exit 0
