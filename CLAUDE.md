# CLAUDE.md

AstroBot — production-style RAG astronomy chatbot. Python/FastAPI backend, React 19 + TS + Vite + Tailwind 4 frontend, Terraform/AWS infra. Deep architecture and roadmap live in [README.md](README.md); this file is the operational contract for working in the repo.

## Working agreements

- **No emojis. Anywhere.** Responses, code, comments, commit messages, corpus entries. The product enforces the same rule on itself via `SYSTEM_PROMPT` in `src/bot_controller.py` — keep them consistent.
- **Verify before claiming done.** There is no test suite yet (see Verification). Run the relevant command and observe real output before saying a change works.
- **Match the existing commit style:** conventional commits with scope — `feat(web):`, `fix(api):`, `chore:`.

## Usage and cost discipline

Two separate budgets — never conflate them:

- **Claude Code plan usage** (the architect's subscription). Parallel sessions, agent teams, and subagents multiply burn. Defaults: one session per task; at most ONE parallel pair (two worktree sessions) at a time; no subagents or agent teams unless the architect asks. The architect checks `/usage` before kicking off parallel work and after finishing it.
- **AstroBot's own Anthropic API key** (the product's spend). Prod chat is hard-capped by `DAILY_BUDGET_USD` in `api/limits.py`. The eval harness BYPASSES that cap (it constructs its own client) — only the faithfulness eval spends tokens (roughly tens of cents per run on Sonnet); run it deliberately and never in CI, loops, or hooks.

## Repo layout

- `api/` — FastAPI server (deployed to EC2 via Docker). Endpoints, tiered pipeline wrapper, save guard, pending queue, rate limits.
- `src/` — ML/RAG pipeline: scrape, clean, train DistilBERT, build ChromaDB, eval harness, `bot_controller.py` (source of truth for routing constants).
- `web/` — React frontend (Vite build to S3 + CloudFront).
- `data/` — corpus YAML, orbital elements, eval set, generated ChromaDB.
- `infra/terraform/` — full AWS stack as modules.
- `scripts/` — deploy + admin CLIs.
- `models/`, `logs/` — generated/untracked.

## Commands

All Python commands run **from the repo root** (the `api` package imports `src/` via a path shim).

**Backend**
- Env setup (once): `/usr/local/bin/python3.11 -m venv .venv && .venv/bin/pip install -r requirements_local.txt` — use 3.11: system python3 is 3.9 (cannot import this codebase's `X | None` annotations) and the Intel-mac torch 2.2 pin has no 3.13 wheels. Prod/Linux uses `requirements.txt`.
- Tests: `.venv/bin/python -m pytest -q tests/`
- Full API (RAG + models): `uvicorn api.api_server:app --reload --port 8000`
- Light dev API (trajectory only, no torch/Chroma/RAG — fast UI iteration): `uvicorn api.dev_server:app --reload --port 8000`
- Evals: `python src/run_evals.py --eval all` (or `retrieval` / `faithfulness` / `intent`)
- Rebuild vector store: `python src/build_vector_store.py`
- Retrain intent classifier: `python src/train_bert.py`
- Admin review queue: `python scripts/review_pending.py`

**Frontend** (from `web/`)
- `npm install` then `npm run dev` — Vite dev server (default `:5173`), proxies `/api` to `:8000`.
- `npm run build` (runs `tsc -b && vite build`), `npm run typecheck`, `npm test` (vitest).

**Local loop:** start an API on `:8000` (`dev_server` for UI-only, `api_server` for full RAG) + `npm run dev`; the browser hits Vite, which proxies `/api` to the backend.

**Deploy:** backend `scripts/deploy-image.sh`, frontend `scripts/deploy-web.sh`, secrets `scripts/set-secrets.sh`.

## Verification (read this)

- **Run the tests:** `.venv/bin/python -m pytest -q tests/` from the repo root (save guard, trajectory fast path, tier routing — LLM faked, no torch/Chroma/network) and `npm test` from `web/` (vitest; narration planner so far).
- **Test discipline:** files headed `# LOCKED` (py) or `// LOCKED` (ts) are frozen acceptance criteria. Never edit one to make an implementation pass — a criteria change is a new architect-approved task (see `TASKS.md`). The `TaskCompleted` hook (`.claude/hooks/test-gate.sh`) runs both suites (web only where `web/node_modules` exists) and blocks task completion while red; `lock-guard.sh` warns on any edit to a locked file.
- CI (`.github/workflows/ci.yml`) runs both locked suites plus the web build on every push/PR, installing only `requirements-test.txt` — never the torch stack, never the evals.
- The eval harness (`src/run_evals.py`) is a separate quality gate (retrieval / intent / faithfulness scores) — it is not a substitute for the unit tests, nor vice versa.
- Component/UI behavior beyond the pure planners is still uncovered: verify with `npm run dev` and look. For API changes beyond unit coverage, `curl` against `/api/chat`. Never assert a change works without running something.

## Canonical patterns (the invariants)

**Tiered routing** — `api/chat_engine.py::chat_once`. Order: trajectory fast path -> Tier 1 corpus-direct -> budget-exhausted fallback -> Tier 2/3 LLM. **Tier 1 and the trajectory path make zero LLM calls** — that is the cost design; preserve it. Thresholds are constants in `src/bot_controller.py` (`DIRECT_ANSWER_THRESHOLD`, `RETRIEVAL_RELEVANCE_THRESHOLD`); `FALLBACK_THRESHOLD` is in `chat_engine.py`. Current settings: Tier 1 >= 0.65, Tier 2 0.30-0.65, Tier 3 < 0.30. Reference the constants — do not hardcode these numbers elsewhere.

**Save guard / corpus integrity** — `api/save_guard.py`. Every Tier 2/3 answer auto-stages to `data/pending_corpus.yml` and is **not retrieved in chat until a human approves it** via `scripts/review_pending.py`. Never let a generated answer reach the live corpus without that gate. The guard is conservative by design (structural -> intent `general_chat` veto -> Haiku judge): reject on any signal. Corpus poisoning is hard to reverse.

**Response contract** — `ChatResponse` in `api/api_server.py`: `{answer, tier, similarity, sources[], fallback, tokens?, cost_usd?, trajectory?}`. Three places mirror this shape and must change together: `api/api_server.py`, `api/dev_server.py`, and `web/src/types.ts`.

## Auth / security reality

The production API (`api/api_server.py`) has **no auth**. The abuse ceiling is a per-IP sliding-window rate limit plus a hard daily USD cap on Anthropic spend (`api/limits.py`). `/api/login` exists **only** in `api/dev_server.py` as a static-token stub; `PyJWT` in `requirements_local.txt` and `web/src/components/LoginGate.tsx` are vestigial and not wired in. Older docs that say "JWT-authed" are stale — trust the code.

## Agent ownership boundaries

Multi-agent runs are gated by `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in
`.claude/settings.json`. When the architect authorizes an agent team, ownership
is strictly partitioned:

| Agent | Owns | Must NOT touch |
|-------|------|----------------|
| [A] api agent | `api/`, `tests/` | `src/`, `web/`, `infra/` |
| [M] ML agent | `src/`, `data/` | `api/`, `web/`, `infra/` |
| [W] web agent | `web/` | `api/`, `src/`, `infra/` |
| [R] reviewer | read-only everywhere | no writes |

Cross-boundary writes require architect approval as a new task. An agent may
read files outside its boundary for context but must not edit them.

The `scope-check.sh` hook (runs on `TaskCreated`) reminds agents to declare
a locked-tests dependency before any implementation task.

## Generated / do not edit

`data/chroma_db/` (rebuild with `build_vector_store.py`), `models/` (rebuild with `train_bert.py`), `data/pending_corpus.yml` (review queue), `logs/`, `web/dist/`, `web/node_modules/`, `.env`.

## Known drift (fix candidates)

- README says "structured JSON logging" but `logs/astrobot.log` is pipe-delimited text.
- README cites 340 corpus pairs; the store loads ~360 chunks.
- README lists `/api/login` as a production endpoint; it is not (see Auth reality).
