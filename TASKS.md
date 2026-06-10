# Task pool — AstroBot

Architect-seeded task list. A lead Claude Code session reads this and creates
the entries as actual tracked tasks; the `depends on` lines make tests-first
structural rather than optional. The `TaskCompleted` hook runs the locked
pytest suite before any task is allowed to close — enforced, not advisory.

Task states: pending -> in_progress -> completed.

## Legend
- [H] = human/architect-owned (defines or approves; does not implement)
- [A] = api agent (owns `api/`)
- [M] = ML agent (owns `src/`, `data/`)
- [W] = web agent (owns `web/`)
- [R] = review (reviewer agent or human)

## The rule that holds it together

No implementation task may begin before its locked-tests task completes. An
implementing agent may NOT edit a `# LOCKED` test to pass. If a criterion must
change, that is a NEW [H] task — never a quiet edit by the agent trying to
satisfy it.

## Stage 0 — Harness bootstrap (done 2026-06-10)

1. [H] Approve harness design (CLAUDE.md + NOTES.md) — STATUS: done
2. [A] Locked tests pinning current behavior: save guard, trajectory,
       tier routing (26 tests, LLM faked, zero network) — STATUS: done
3. [A] Hook gate: `.claude/settings.json` + `test-gate.sh` (exit 2 blocks)
       + `lock-guard.sh` — STATUS: done, verified blocking on a planted red

## Stage 1 — Chatbot fix (NEXT)

4. [H] Describe the chatbot bug and define "done" (acceptance criteria)
       - STATUS: OPEN — architect fills this in to start the stage
       - template: symptom, expected behavior, 3-5 concrete input/output
         examples that must hold afterward
5. [A/M] Write locked tests encoding those criteria
       - depends on: task 4
6. [H] Lock the tests (freeze acceptance criteria)
       - depends on: task 5
7. [A/M] Implement the fix to pass the locked tests
       - depends on: task 6  <-- cannot start before tests exist
8. [R] Review the fix

## Stage 2 — Roadmap pool (seed from README "To do"; same 5-step shape each)

9.  CI: GitHub Actions workflow running `pytest -q tests/` on every push
    (deploy via OIDC later)
10. Add a `request_trajectory` intent to the DistilBERT classifier so orbit
    questions stop leaking into `define_concept`
11. Hybrid BM25 + dense retrieval; eval-set audit; grow eval set past 20
12. Adversarial eval suite — prompt-injection cases against `/api/chat` and
    the save guard
13. vitest for `web/` — `kepler.ts` solver, typed `api.ts` client
14. Layered durability — S3 versioned backup of EBS corpus on every save
