# CLAUDE.md

AstroBot — production-style RAG astronomy chatbot. Python/FastAPI backend, React 19 + TS + Vite + Tailwind 4 frontend, Terraform/AWS infra. Deep architecture and roadmap live in [README.md](README.md); this file is the operational contract for working in the repo.

## Working agreements

- **No emojis. Anywhere.** Responses, code, comments, commit messages, corpus entries. The product enforces the same rule on itself via `SYSTEM_PROMPT` in `src/bot_controller.py` — keep them consistent.
- **Verify before claiming done.** There is no test suite yet (see Verification). Run the relevant command and observe real output before saying a change works.
- **Match the existing commit style:** conventional commits with scope — `feat(web):`, `fix(api):`, `chore:`.

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
- Install (Intel mac, pinned older stack): `pip install -r requirements_local.txt` — prod/Linux uses `requirements.txt`.
- Full API (RAG + models): `uvicorn api.api_server:app --reload --port 8000`
- Light dev API (trajectory only, no torch/Chroma/RAG — fast UI iteration): `uvicorn api.dev_server:app --reload --port 8000`
- Evals: `python src/run_evals.py --eval all` (or `retrieval` / `faithfulness` / `intent`)
- Rebuild vector store: `python src/build_vector_store.py`
- Retrain intent classifier: `python src/train_bert.py`
- Admin review queue: `python scripts/review_pending.py`

**Frontend** (from `web/`)
- `npm install` then `npm run dev` — Vite dev server (default `:5173`), proxies `/api` to `:8000`.
- `npm run build` (runs `tsc -b && vite build`), `npm run typecheck`.

**Local loop:** start an API on `:8000` (`dev_server` for UI-only, `api_server` for full RAG) + `npm run dev`; the browser hits Vite, which proxies `/api` to the backend.

**Deploy:** backend `scripts/deploy-image.sh`, frontend `scripts/deploy-web.sh`, secrets `scripts/set-secrets.sh`.

## Verification (read this)

- **No unit/integration tests exist** — no pytest, no vitest, anywhere. The only automated check is the eval harness (`src/run_evals.py`), which scores retrieval / intent / faithfulness *quality*, not correctness of the API, save guard, trajectory math, tier routing, or UI.
- Until a real test layer lands (next planned workstream), verify by running: for API, `curl` against `/api/chat`; for web, `npm run dev` and look; for the pipeline, the eval harness. Never assert a change works without doing this.

## Canonical patterns (the invariants)

**Tiered routing** — `api/chat_engine.py::chat_once`. Order: trajectory fast path -> Tier 1 corpus-direct -> budget-exhausted fallback -> Tier 2/3 LLM. **Tier 1 and the trajectory path make zero LLM calls** — that is the cost design; preserve it. Thresholds are constants in `src/bot_controller.py` (`DIRECT_ANSWER_THRESHOLD`, `RETRIEVAL_RELEVANCE_THRESHOLD`); `FALLBACK_THRESHOLD` is in `chat_engine.py`. Current settings: Tier 1 >= 0.65, Tier 2 0.30-0.65, Tier 3 < 0.30. Reference the constants — do not hardcode these numbers elsewhere.

**Save guard / corpus integrity** — `api/save_guard.py`. Every Tier 2/3 answer auto-stages to `data/pending_corpus.yml` and is **not retrieved in chat until a human approves it** via `scripts/review_pending.py`. Never let a generated answer reach the live corpus without that gate. The guard is conservative by design (structural -> intent `general_chat` veto -> Haiku judge): reject on any signal. Corpus poisoning is hard to reverse.

**Response contract** — `ChatResponse` in `api/api_server.py`: `{answer, tier, similarity, sources[], fallback, tokens?, cost_usd?, trajectory?}`. Three places mirror this shape and must change together: `api/api_server.py`, `api/dev_server.py`, and `web/src/types.ts`.

## Auth / security reality

The production API (`api/api_server.py`) has **no auth**. The abuse ceiling is a per-IP sliding-window rate limit plus a hard daily USD cap on Anthropic spend (`api/limits.py`). `/api/login` exists **only** in `api/dev_server.py` as a static-token stub; `PyJWT` in `requirements_local.txt` and `web/src/components/LoginGate.tsx` are vestigial and not wired in. Older docs that say "JWT-authed" are stale — trust the code.

## Generated / do not edit

`data/chroma_db/` (rebuild with `build_vector_store.py`), `models/` (rebuild with `train_bert.py`), `data/pending_corpus.yml` (review queue), `logs/`, `web/dist/`, `web/node_modules/`, `.env`.

## Known drift (fix candidates)

- README says "structured JSON logging" but `logs/astrobot.log` is pipe-delimited text.
- README cites 340 corpus pairs; the store loads ~360 chunks.
- README lists `/api/login` as a production endpoint; it is not (see Auth reality).
