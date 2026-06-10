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

## Stage 1 — Chatbot fix: narration dedupe (done 2026-06-10, review open)

4. [H] Describe the bug and define "done" — STATUS: done
       - Bug: re-entering an already-toured view (e.g. planet -> back to
         system) re-narrated the same intro via a fresh API call.
       - Criteria (architect-approved): first visit narrates via API;
         revisits print a short local "re-entering" line at zero token
         cost; planets tracked individually; galaxy never narrates;
         same-view re-fires say nothing; a narration skipped mid-exchange
         is not marked toured; ledger is in-memory so it resets with the
         chat log on reload (the two must never disagree).
5. [W] Locked tests encoding the criteria — STATUS: done
       (web/src/narration.test.ts, 9 tests; vitest pulled forward from
       task 13 to support this)
6. [H] Lock the tests — STATUS: done (LOCKED header, lock-guard covers
       // LOCKED and *.test.* paths now)
7. [W] Implement — STATUS: done (web/src/narration.ts pure planner +
       ConsoleChat ledger wiring; planner test-pinned, wiring typechecked;
       browser click-through still worth doing at review)
8. [R] Review the fix — STATUS: OPEN — architect reviews the pushed diff

## Stage 2 — Roadmap pool (seed from README "To do"; same 5-step shape each)

9.  CI: GitHub Actions workflow running `pytest -q tests/` on every push
    (deploy via OIDC later)
10. Add a `request_trajectory` intent to the DistilBERT classifier so orbit
    questions stop leaking into `define_concept`
11. Hybrid BM25 + dense retrieval; eval-set audit; grow eval set past 20
12. Adversarial eval suite — prompt-injection cases against `/api/chat` and
    the save guard
13. vitest for `web/` — scaffolding DONE via Stage 1 (`npm test`, gate
    runs it); still pooled: `kepler.ts` solver, typed `api.ts` client
14. Layered durability — S3 versioned backup of EBS corpus on every save
15. Session persistence across reloads — store chat log + narration
    ledger together (localStorage); they must persist or reset as one
16. Per-user long-term memory — server-side, requires identity/auth
    first (prod API has none today); architect decision on scope
