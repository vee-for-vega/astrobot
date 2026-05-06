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
| **Hit Rate @ 3** | 35.0% (7/20) |
| **MRR** | 0.325 |

The 35% hit rate reflects a strict matching criterion — many queries retrieve semantically correct answers that are phrased differently than the expected source. For example, "What's the temperature on Mercury?" retrieves "how hot is mercury?" at rank 1 (distance 0.27), which is the right answer under a different question. The eval framework counts this as a miss because the `expected_source` string doesn't match. Relaxing the match criteria or expanding the eval set are planned improvements.

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

Hosted on AWS (CloudFront + EC2 + S3). Password-gated to keep token spend bounded.
URL and password are on my resume.

The site is a CLI-style terminal — type `help` for commands. Commands like `tier`,
`sources`, and `stats` expose the underlying retrieval and routing so you can
see *how* an answer was produced, not just what it said.

## Project Structure

```
├── requirements.txt
│
├── api/                         # FastAPI server (deployed to EC2 via Docker)
│   ├── api_server.py            # Endpoints: /login, /chat, /health, /stats
│   ├── auth.py                  # JWT (HS256) issuing + verification
│   ├── chat_engine.py           # Programmatic tiered pipeline
│   ├── limits.py                # Rate limit + daily token budget cap
│   └── Dockerfile               # Multi-stage, non-root, prebaked HF model
│
├── web/                         # Static frontend (S3 + CloudFront)
│   ├── index.html
│   ├── terminal.js              # CLI state machine, vanilla JS
│   └── style.css
│
├── src/                         # Original ML/RAG pipeline
│   ├── scrape_data.py
│   ├── clean_corpus.py
│   ├── train_bert.py            # Fine-tunes DistilBERT for intent
│   ├── build_vector_store.py    # Embeds corpus into ChromaDB
│   ├── bot_controller.py         # Tiered routing, RAG, Claude API
│   └── run_evals.py             # Evaluation harness
│
├── data/
│   ├── astronomy_corpus.yml     # 323 Q&A pairs from NASA + Cool Cosmos
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
│   ├── set-secrets.sh           # Set Anthropic key, demo password, JWT key
│   ├── deploy-image.sh          # Build, push to ECR, restart service
│   └── deploy-web.sh            # Sync to S3, invalidate CloudFront
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
            │   ├─ JWT auth          │   │  read via OAC      │
            │   ├─ rate limit        │   └────────────────────┘
            │   ├─ budget cap        │
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
            │  SSM SecureString (3 KMS-encrypted)     │
            │   /astrobot/anthropic_api_key           │
            │   /astrobot/auth_password               │
            │   /astrobot/jwt_signing_key             │
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

## Deploy

```bash
# 1. Provision (one-time)
cd infra/terraform/bootstrap
terraform apply -var="account_suffix=<your-suffix>"

cd ../envs/prod
echo 'bucket_suffix = "<your-suffix>"' > terraform.tfvars
terraform apply

# 2. Set the three secrets (one-time, prompts for values)
./scripts/set-secrets.sh

# 3. Build + push the bot image
./scripts/deploy-image.sh

# 4. Sync the frontend
./scripts/deploy-web.sh
```

The site URL is in `terraform output site_url`.

## Cost

Roughly $19/mo for the always-on stack (EC2 t3.small + 30 GB root EBS + 10 GB data EBS + CloudFront).
Anthropic API spend is capped at $1/day in-app. When the budget is exhausted,
Tier 1 corpus answers continue to serve, with a banner explaining the cap.

---

## Roadmap

### Completed (Original project)
- [x] Claude API integration
- [x] RAG pipeline (ChromaDB + sentence-transformers, cosine similarity)
- [x] Tiered response routing (Tier 1 direct / Tier 2 RAG / Tier 3 LLM-only)
- [x] Content freshness system (6-month refresh cycle with Claude enrichment)
- [x] Corpus learning loop (human-in-the-loop answer approval)
- [x] DistilBERT intent classifier (fine-tuned, 84.2% accuracy)
- [x] Evaluation harness (retrieval hit rate, faithfulness, intent classification)
- [x] Structured JSON logging with retrieval metadata

### Completed (Production deployment)
- [x] **IaC** — Terraform: VPC, IAM, S3, ECR, EC2 + Docker + EBS, CloudFront with OAC, SSM SecureString secrets
- [x] **FastAPI web server** — JWT auth, sliding-window rate limit, daily token-budget cap with Tier 1 graceful fallback
- [x] **Frontend UI** — vanilla-JS CLI terminal with command history and `tier`/`sources`/`stats` commands
- [x] **Persistent vector store** — dedicated EBS gp3 volume for ChromaDB + corpus YAML, separate from EC2 root, survives instance replacement

### In Progress
- [ ] **CI/CD via GitHub Actions + OIDC** — keyless deploys, auto-eval on push
- [ ] **Improve eval framework** — fuzzy/semantic match for retrieval, expand test set beyond 20 queries
- [ ] **Improve intent classifier** — more training data, expand math keyword shortcuts
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

Python, PyTorch, Anthropic Claude API, ChromaDB, Sentence-Transformers, DistilBERT, SymPy, Terraform, Docker, AWS (EC2, S3, IAM)

## License

MIT

---

*Built with PyTorch, ChromaDB, and NASA open data.*
