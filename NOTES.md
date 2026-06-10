# AstroBot — Agentic Engineering Handoff

> **STATUS 2026-06-10 — Phase 0 COMPLETE.** Everything in "What to build"
> below now exists in the repo: `tests/` (26 locked tests, green),
> `.claude/settings.json` + `test-gate.sh` (verified blocking) +
> `lock-guard.sh`, and `TASKS.md`. Env: `.venv` on python3.11 (see
> CLAUDE.md Commands). Still open, pooled in TASKS.md: scope-check hook,
> agent-teams env flag, vitest for web/, CI on push. New sessions: read
> CLAUDE.md (automatic) and TASKS.md — Stage 1 awaits architect criteria.

Hand this to a fresh Claude Code session to continue turning AstroBot into an
agentic-style project. It is self-contained — you do not need the prior chat.

## Start here

- Repo: `~/Desktop/astrobot` — GitHub `git@github.com:vee-for-vega/astrobot.git`, branch `main`.
- Read `CLAUDE.md` at the repo root first. It is the operational contract: run/build commands, the three invariants (tier routing, save guard, response contract), the no-auth reality, and the explicit note that **no test suite exists yet**.
- Current state: `CLAUDE.md` was just written and pushed (commits `280d92f`, `8b80cd8`). There is **no `.claude/` directory and no tests yet**. That is the work below.

## The goal

Turn AstroBot into an agentic-style project modeled on my reference project
`tiktok-engagement-pipeline` (lives at `~/Downloads/tiktok-engagement-pipeline`
on my main Mac only). The realization driving this: "start testing" is not just
adding tests. In the agentic model, tests are the load-bearing part of a
harness, and `.claude/settings.json` hooks are what make them **enforced**
rather than advisory. Tests and `settings.json` are one system — build both.

## What to build (three parts of one harness)

### 1. pytest suite — tests-first, locked

- Add `pytest` as a dev dependency; create `tests/` with `tests/__init__.py`. Run from the **repo root** (the `api` package imports `src/` via a path shim — see CLAUDE.md). `pytest -q tests/`.
- First targets — highest value, pure logic, no network:
  - `api/save_guard.py` — the reject-on-any-signal validator. Assert the length caps, the compound+generative rejection, and the `general_chat` intent veto. Pure and high-value (corpus integrity).
  - `api/trajectory.py` — deterministic Kepler math + fuzzy planet match. Assert known orbits, typo tolerance ("marz" -> mars), and that a non-orbit query returns `None`.
  - `api/chat_engine.py::chat_once` — tier selection. **Mock the Anthropic client** and assert: a trajectory query and a Tier-1 corpus hit make ZERO LLM calls; the budget-exhausted path returns the fallback or raises `BudgetExhausted`. This protects the cost design.
- Locked-test convention (from the template): freeze acceptance-criteria tests with a `# LOCKED` header comment. A `# LOCKED` test encodes approved criteria and must NOT be edited by the agent implementing against it. If a criterion must change, that is a separate, deliberate decision — never a quiet edit to make code pass.
- The existing eval harness (`src/run_evals.py`) is a **separate** gate — it scores RAG/intent/faithfulness *quality*, not code correctness. Keep it; it is not a substitute for these unit tests.
- Later: `vitest` for `web/` (the `kepler.ts` solver, the typed `api.ts` client, `OrbitCard` rendering).

### 2. `.claude/settings.json` + hooks — the enforcement layer

This is the `settings.json` piece. Mirror the tiktok setup. `.claude/settings.json` wires hooks to events:

- `TaskCompleted` -> `.claude/hooks/test-gate.sh`: runs `pytest -q tests/`; **exit 2 to block**. Critical detail: exit 2 is the ONLY blocking exit code in Claude Code hooks — exit 1 is treated as non-blocking and would let a failing task close anyway. Pass -> exit 0. This makes "tests pass" a structural precondition for closing any task. Keystone script:
  ```bash
  #!/bin/bash
  cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
  if pytest -q tests/ > /tmp/pytest_out.txt 2>&1; then
    exit 0
  else
    echo "Task blocked: tests failing. Fix the code; do NOT edit tests to pass." >&2
    tail -n 20 /tmp/pytest_out.txt >&2
    exit 2
  fi
  ```
- `PostToolUse` (matcher `Edit|Write`) -> `.claude/hooks/lock-guard.sh`: read the hook JSON from stdin, extract `tool_input.file_path`; if it is under `tests/` and contains `# LOCKED`, print a stderr warning so the agent reverts. PostToolUse cannot un-edit, but the warning self-corrects the agent and leaves an audit trail.
- `TaskCreated` -> `.claude/hooks/scope-check.sh` (optional): if a task looks like implementation ("implement"/"build the") but mentions no test/criteria, remind that implementation tasks must depend on a locked-tests task. Exit 0 with a stderr nudge (non-blocking).
- `.claude/settings.json` is committed (shared); add `.claude/settings.local.json` to `.gitignore` (personal overrides, not shared).
- Set `env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in settings only if going multi-agent (tiktok does). For a single-agent start, the hooks alone are the win.
- Reference copies to adapt live at `~/Downloads/tiktok-engagement-pipeline/.claude/` (original Mac only) — the distilled essentials above are enough to rebuild them anywhere.

### 3. `TASKS.md` — the ticket pool

- Create `TASKS.md` as a dependency-ordered task pool, like tiktok's. The rule that makes it real: an implementation task `depends on` its locked-tests task and cannot start before it. States: pending -> in_progress -> completed.
- Seed first tickets (tests-first; the targets in part 1 already have implementations, so write tests to pin current behavior, then refactor under green):
  1. Write locked tests for `save_guard` -> lock -> review.
  2. Write locked tests for `trajectory` -> lock -> review.
  3. Write locked tests for `chat_engine` tier routing (mock LLM) -> lock -> review.
- Then pull from the README "To do" roadmap: CI/CD via GitHub Actions + auto-eval on push; hybrid BM25 + dense retrieval; add a `request_trajectory` intent; adversarial / prompt-injection eval against `/api/chat` and the save guard.
- Each ticket: small, one deliverable. Add an owner tag if multi-agent — natural ownership boundaries are `api/` vs `src/` vs `web/` vs `infra/`.

## Suggested order

1. pytest scaffolding + the three locked test files (save_guard, trajectory, chat_engine). Get them green.
2. `.claude/settings.json` + `test-gate.sh` + `lock-guard.sh`; verify the gate actually blocks by making a test fail on purpose once.
3. `TASKS.md` seeded from the roadmap.
4. Later: agent-teams env + `scope-check.sh`; add "ownership boundaries" + "test discipline" sections to CLAUDE.md; vitest for web; a CI workflow that runs pytest on push.

## Watch out for

- Run pytest from the **repo root**, not from `api/` (import path shim).
- Never let the LLM-touching tests hit the real Anthropic API — mock the client (`bot_controller.client`).
- No emojis anywhere — repo-wide rule, also stated in CLAUDE.md.
