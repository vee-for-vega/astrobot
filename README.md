```text
             (o)
           ___I__
         / [_____]\
        |          |
       *|  [0]  [0]|*        
        |          |
        |  [|||||] |         AstroBot — Production RAG Astronomy Chatbot
         \________/
```
## AstroBot

A retrieval-augmented generation (RAG) chatbot that answers astronomy questions using a curated NASA knowledge base, semantic vector retrieval, and Claude API generation — built as a production-style ML system with evaluation, tiered response routing, and cloud infrastructure.

Originally developed for **Principles of Machine Learning (CSC 525)** at **Colorado State University**. Now being actively developed as an independent project targeting production ML/AI engineering practices.

---

## The Problem

General-purpose LLMs can answer astronomy questions, but they hallucinate, can't cite sources, and cost tokens on every call — even for questions that have known, verified answers. AstroBot solves this with a tiered architecture: verified NASA data is served instantly when available, LLM generation is used only when needed, and every answer can be traced back to its source.

**Input:** Natural language astronomy questions
**Output:** Grounded answers from NASA data or Claude-augmented responses, with retrieval metadata and confidence scores

---

## Architecture

```
User Query
    │
    ▼
┌──────────────────────────┐
│  DistilBERT Intent       │  Fine-tuned classifier routes queries
│  Classifier              │  to the right handler
└────────────┬─────────────┘
             │
       ┌─────┴───────┐
       ▼             ▼
┌──────────┐  ┌───────────────────────────────────────────────┐
│  Math    │  │  Tiered Response System                       │
│  Module  │  │                                               │
│  SymPy   │  │  1. Embed query (MiniLM-L6-v2)                │
└──────────┘  │  2. Search ChromaDB (cosine, top-3)           │
              │  3. Route by similarity score:                │
              │     ├─ Tier 1 (≥0.65): corpus answer direct   │
              │     ├─ Tier 2 (0.30–0.65): RAG + Claude       │
              │     └─ Tier 3 (<0.30): Claude only            │
              │  4. Content freshness: refresh Tier 1 answers │
              │     with Claude every 6 months                │
              └───────────────────────────────────────────────┘
```

### Tiered Response Routing

The system minimizes LLM API costs while maintaining answer quality. Not every question needs Claude.

| Tier | Similarity | What Happens | Tokens Used |
|------|-----------|--------------|-------------|
| **Tier 1** | ≥ 0.65 | Corpus answer returned directly | **Zero** |
| **Tier 1 + Refresh** | ≥ 0.65 (stale) | Claude enriches the corpus answer, saves it back | One-time cost |
| **Tier 2** | 0.30 – 0.65 | Retrieved chunks injected as context → Claude generates | Per-query |
| **Tier 3** | < 0.30 | Claude answers from own knowledge (no useful context) | Per-query |

### Content Freshness System

Tier 1 answers are periodically refreshed by Claude to stay current. Each corpus entry tracks its last refresh date. After 6 months, the next Tier 1 hit sends the existing answer to Claude for enrichment — preserving the original NASA facts while supplementing with newer information. The enriched answer saves back to both the YAML corpus and ChromaDB, and the timer resets.

---

## Current Eval Results

Evaluated on a curated test set of 20 retrieval queries, 19 intent classification queries, and 10 faithfulness queries (RAG vs no-RAG comparison using LLM-as-judge).

### Retrieval Quality

| Metric | Score |
|--------|-------|
| **Hit Rate @ 3** | 75.0% (15/20) |
| **MRR** | 0.700 |

The matcher does a substring check first, then falls back to cosine similarity (≥ 0.75) between the expected and retrieved questions using the same MiniLM embeddings as retrieval. Of the 15 hits, 7 are exact substring matches and 8 come from the semantic fallback — those are queries like "What's the temperature on Mercury?" that retrieve "how hot is mercury?" at rank 1, which the old strict-substring matcher counted as a miss. The 5 remaining misses split into a real ranking failure (the exact-text question gets buried under a topically related entry), an eval-label bug (expected source doesn't match what's actually in the corpus), and two paraphrases sitting just below the threshold. Next: hybrid BM25 + dense retrieval, eval-set audit, and growing the test set past 20 queries.

### Intent Classification (DistilBERT)

| Intent | Precision | Recall | F1 | Support |
|--------|-----------|--------|----|---------|
| define_concept | 0.667 | 0.800 | 0.727 | 5 |
| general_chat | 1.000 | 1.000 | 1.000 | 5 |
| historical_fact | 1.000 | 0.800 | 0.889 | 5 |
| request_math | 0.750 | 0.750 | 0.750 | 4 |
| **Overall** | | | **Macro-F1: 0.842** | **Accuracy: 84.2%** |

The main confusion is between `define_concept` and `request_math` — "What is the formula for gravitational force?" gets classified as `define_concept` instead of `request_math`. The keyword shortcut catches explicit words like "calculate" and "solve" but misses formula-related questions. More training data and additional math keywords would improve this.

### Generation Faithfulness (RAG vs No-RAG)

| Metric | RAG | No-RAG |
|--------|-----|--------|
| **Faithfulness / Accuracy** | 4.11 / 5 | 4.90 / 5 |
| **Relevance** | 4.89 / 5 | 5.00 / 5 |

RAG faithfulness (4.11/5) is lower than no-RAG accuracy (4.90/5) because the LLM-as-judge scores faithfulness as "grounded in provided context" — when Claude supplements corpus data with its own knowledge (which is accurate), the judge penalizes it for going beyond the context. The no-RAG accuracy score reflects that Claude's astronomy knowledge is already strong. The value of RAG is **traceability** — knowing where the answer came from — not just accuracy.

---

## Live demo

Hosted on AWS (CloudFront + EC2 + S3). URL is on my resume.

The site is a React chat UI built around the trajectory-visualization product:
ask about a planet's orbit and the bot returns an animated 2D orbit card
(top view + side view) inline as an answer. Other astronomy questions
hit the tiered RAG pipeline; generated answers carry a "not yet verified"
disclaimer and are auto-staged for admin review before joining the corpus.

## Project Structure

```
├── requirements.txt
│
├── api/                         # FastAPI server (deployed to EC2 via Docker)
│   ├── api_server.py            # Endpoints: /login, /chat, /health, /stats
│   ├── chat_engine.py           # Tiered pipeline + auto-stage tier 2/3 answers
│   ├── trajectory.py            # Deterministic orbit fast path, fuzzy planet match
│   ├── save_guard.py            # 3-layer validator (structural / intent / LLM-as-judge)
│   ├── pending.py               # Admin-review queue (data/pending_corpus.yml)
│   ├── dev_server.py            # Lightweight UI-only local server (no torch/chroma)
│   ├── limits.py                # Rate limit + daily token budget cap
│   └── Dockerfile               # Multi-stage, non-root, prebaked HF model
│
├── web/                         # React frontend (Vite build → S3 + CloudFront)
│   ├── package.json
│   ├── vite.config.ts           # /api dev proxy + tailwind plugin
│   ├── index.html
│   ├── public/robot.png         # Assistant avatar
│   └── src/
│       ├── main.tsx             # React entry
│       ├── App.tsx              # Auth gate + chat shell
│       ├── api.ts               # Typed /api client
│       ├── types.ts             # ChatResponse, Trajectory, OrbitalElements
│       ├── kepler.ts            # Analytical solver + ellipse path emitter
│       ├── components/
│       │   ├── Chat.tsx
│       │   ├── Message.tsx      # Text or inline OrbitCard
│       │   ├── OrbitCard.tsx    # Top + side view answer strip
│       │   ├── TopView.tsx      # Animated SVG ellipse
│       │   ├── SideView.tsx     # Animated inclination line
│       │   ├── PlanetInfo.tsx
│       │   ├── PromptInput.tsx
│       │   ├── WelcomeHero.tsx
│       │   ├── LoginGate.tsx
│       │   ├── RobotAvatar.tsx
│       │   ├── SuggestionChips.tsx
│       │   └── ThinkingIndicator.tsx
│       └── data/solar-system.json
│
├── src/                         # ML/RAG pipeline
│   ├── scrape_data.py
│   ├── clean_corpus.py
│   ├── train_bert.py            # Fine-tunes DistilBERT for intent
│   ├── build_vector_store.py    # Embeds corpus into ChromaDB
│   ├── bot_controller.py        # Tiered routing, RAG, Claude API, corpus learning
│   └── run_evals.py             # Evaluation harness
│
├── data/
│   ├── astronomy_corpus.yml     # 323 Q&A pairs from NASA + Cool Cosmos
│   ├── orbital_elements.yml     # J2000 Keplerian elements for 8 planets
│   ├── pending_corpus.yml       # Admin-review queue (gitignored)
│   ├── intent_training.csv
│   ├── eval_questions.json
│   └── chroma_db/               # ChromaDB vector store (generated)
│
├── infra/terraform/             # IaC for the whole AWS stack
│   ├── bootstrap/               # S3 + native locking for remote state
│   ├── envs/prod/               # composes the modules
│   └── modules/
│       ├── network/             # VPC, public subnets, IGW, routing
│       ├── iam/                 # EC2 role with SSM + CloudWatch
│       ├── storage/             # Private S3 bucket for the static site
│       ├── ecr/                 # Private Docker registry
│       ├── compute/             # EC2 + EBS + EIP + secrets in SSM
│       └── cdn/                 # CloudFront with OAC, dual origin
│
├── scripts/
│   ├── set-secrets.sh           # Set Anthropic API key in SSM
│   ├── deploy-image.sh          # Build, push to ECR, restart service
│   ├── deploy-web.sh            # Vite build → S3 sync → CloudFront invalidate
│   └── review_pending.py        # Admin CLI: approve/reject pending corpus entries
│
├── models/                      # Fine-tuned DistilBERT (generated)
└── logs/                        # Structured logs (not tracked)
```

## Architecture (AWS deployment)

```
                          ┌──────────────────────┐
                          │  Browser             │
                          └──────────┬───────────┘
                                     │ HTTPS
                                     ▼
                          ┌──────────────────────┐
                          │  CloudFront          │  TLS, gzip/brotli, edge cache
                          │  (default cert)      │
                          └─────┬───────────┬────┘
                                │           │
                       /  /api/*│           │/, /index.html, etc.
                                ▼           ▼
            ┌────────────────────────┐   ┌────────────────────┐
            │  EC2 t3.small          │   │  S3 (private)      │
            │  Docker: FastAPI       │   │  HTML/JS/CSS       │
            │   ├─ rate limit (IP)   │   │  read via OAC      │
            │   ├─ budget cap        │   └────────────────────┘
            │   ├─ trajectory branch │
            │   └─ tiered RAG        │
            └────┬─────────┬─────────┘
                 │         │ /app/data bind-mount
                 │         ▼
                 │   ┌──────────────────────────────┐
                 │   │  EBS gp3 10 GB (encrypted)   │
                 │   │  /var/lib/astrobot-data      │
                 │   │   ├─ chroma_db/              │
                 │   │   ├─ astronomy_corpus.yml    │
                 │   │   └─ refresh_tracker.json    │
                 │   └──────────────────────────────┘
                 │ instance role
                 ▼
            ┌─────────────────────────────────────────┐
            │  SSM SecureString (KMS-encrypted)       │
            │   /astrobot/anthropic_api_key           │
            └─────────────────────────────────────────┘
```

## Persistence

ChromaDB and the corpus YAML live on a dedicated 10 GB gp3 EBS volume mounted at
`/var/lib/astrobot-data` on the host, bind-mounted into the container at
`/app/data`. The volume is its own Terraform resource — separate from the EC2
root — so it survives:

- container restarts (deploys via `deploy-image.sh`)
- EC2 replacement (Terraform-driven, e.g. `user_data` changes)

It does **not** survive AZ failure or accidental volume deletion. That's the job
of Layer 3 (S3 versioned backup of the volume's contents on every
`save_to_corpus()` call) — listed in the roadmap.

First boot seeds the volume from the image's baked-in `data/` directory. After
that, the volume is the source of truth and the seed is skipped. To push corpus
changes from local to prod, see `scripts/push-corpus.sh` (planned).

## Roadmap

### Key components

**ML / RAG pipeline**
- Claude API integration with cost-capped budget and Tier 1 graceful fallback
- RAG pipeline — ChromaDB + sentence-transformers (MiniLM-L6-v2), cosine similarity
- Tiered response routing — Tier 1 corpus direct / Tier 2 RAG-augmented / Tier 3 Claude only
- DistilBERT intent classifier — fine-tuned, 84.2% accuracy
- Content freshness system — 6-month refresh cycle with Claude enrichment, original NASA facts preserved
- Evaluation harness — retrieval hit rate, faithfulness, intent classification with LLM-as-judge
- Structured JSON logging with retrieval metadata for offline analysis

**Trajectory visualization**
- Animated 2D orbit cards rendered inline in the chat as answer strips — top view (ellipse from the focus) + side view (inclination relative to the ecliptic)
- Analytical Kepler solver — no N-body simulation; works for any star + planet given six orbital elements
- Deterministic trajectory fast path — zero LLM tokens for orbit questions, fuzzy planet matching (`difflib`) tolerates typos like "marz" or "earths"
- Pure SVG, B&W aesthetic, RAF-driven animation; same component renders solar planets and exoplanets

**Safety and admin workflow**
- Auto-stage every Tier 2/3 answer to a pending corpus for human review before it joins the verified knowledge base
- Three-layer save guard — structural (length, compound-prompt detection) + intent (DistilBERT veto on `general_chat`) + Haiku LLM-as-judge
- Hardened system prompt — refuses compound off-topic prompts and generative content (essays, code, translations) regardless of framing
- CLI admin review tool (`scripts/review_pending.py`) — approve promotes to corpus + ChromaDB, reject marks the entry; never blocks the live chat
- "Generated answer — not yet in the verified corpus" disclaimer on every unverified message

**Web frontend**
- React 19 + TypeScript + Vite + Tailwind 4 single-page app
- Chat UI with centered welcome state, suggestion chips, and inline trajectory cards
- Lightweight dev server (`api/dev_server.py`) — exercises the full UI flow without torch/Chroma/transformers, useful for fast iteration

**Production deployment**
- IaC — Terraform: VPC, IAM, S3, ECR, EC2 + Docker + EBS, CloudFront with OAC, SSM SecureString secrets
- FastAPI web server — sliding-window rate limit and daily Anthropic-spend cap as the abuse ceiling
- Persistent vector store — dedicated EBS gp3 volume for ChromaDB + corpus YAML, separate from EC2 root, survives instance replacement

### To do
- [ ] **CI/CD via GitHub Actions + OIDC** — keyless deploys, auto-eval on push
- [ ] **Improve eval framework** — semantic-match fallback shipped (35% → 75% hit rate); next: hybrid BM25 + dense retrieval, eval-set audit, expand test set beyond 20 queries
- [ ] **Improve intent classifier** — more training data, add a `request_trajectory` intent, expand math keyword shortcuts
- [ ] **Production observability** — Langfuse traces + RAGAS metrics, dashboards for latency / cost / retrieval quality
- [ ] **Adversarial eval suite** — PromptFoo prompt-injection cases against `/api/chat` and the save guard
- [ ] **Pin-the-answer** — let users pin a trajectory card so it stays visible across the conversation
- [ ] **Exoplanet ML pipeline integration** — feed predicted systems into the orbit card UI alongside the solar-system data
- [ ] **Scrape more data** — NASA Science, ESA, textbooks
- [ ] **Layered durability** — S3 versioned backup of EBS contents on every corpus save (Layer 3); migrate to OpenSearch Serverless when corpus exceeds ~10K chunks (Layer 4)
- [ ] **Obsidian knowledge base integration** — ingest structured vaults as RAG sources
- [ ] **LoRA fine-tuning** — Llama/Mistral on the corpus for offline inference

---

## Data Sources

- **Q&A Corpus:** [Cool Cosmos / IPAC Caltech](https://coolcosmos.ipac.caltech.edu/asks) + [NASA Imagine](https://imagine.gsfc.nasa.gov/science/questions/)
- **LLM:** [Anthropic Claude API](https://docs.anthropic.com/)
- **Embeddings:** [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)

## Tech Stack

**Backend:** Python, FastAPI, PyTorch, Anthropic Claude API, ChromaDB, Sentence-Transformers, DistilBERT, SymPy
**Frontend:** React 19, TypeScript, Vite, Tailwind CSS 4
**Infra:** Terraform, Docker, AWS (EC2, S3, CloudFront, IAM, SSM)

## License

MIT

---

*Built with PyTorch, ChromaDB, and NASA open data.*
