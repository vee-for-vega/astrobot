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

## Project Structure

```
├── requirements.txt
├── .env.example
│
├── src/
│   ├── scrape_data.py           # Scrapes Q&A from NASA + Cool Cosmos
│   ├── clean_corpus.py          # Text cleaning pipeline
│   ├── train_bert.py            # Fine-tunes DistilBERT for intent classification
│   ├── build_vector_store.py    # Embeds corpus into ChromaDB
│   ├── bot_controller.py        # Main chatbot — tiered routing, RAG, Claude API
│   └── run_evals.py             # Evaluation harness (retrieval, faithfulness, intent)
│
├── data/
│   ├── astronomy_corpus.yml     # 323 Q&A pairs from NASA + Cool Cosmos
│   ├── intent_training.csv      # Intent classification training data
│   ├── eval_questions.json      # Evaluation test set
│   └── chroma_db/               # ChromaDB vector store (generated)
│
├── models/                      # Fine-tuned DistilBERT (generated, not tracked)
├── logs/                        # Structured logs + eval results (not tracked)
│
└── infra/                       # Terraform + deployment (planned)
    └── terraform/
```

---

## Roadmap

### Completed
- [x] Claude API integration
- [x] RAG pipeline (ChromaDB + sentence-transformers, cosine similarity)
- [x] Tiered response routing (Tier 1 direct / Tier 2 RAG / Tier 3 LLM-only)
- [x] Content freshness system (6-month refresh cycle with Claude enrichment)
- [x] Corpus learning loop (human-in-the-loop answer approval)
- [x] DistilBERT intent classifier (fine-tuned, 84.2% accuracy)
- [x] Evaluation harness (retrieval hit rate, faithfulness, intent classification)
- [x] Structured JSON logging with retrieval metadata

### In Progress
- [ ] **IaC** — Terraform infrastructure (EC2 + S3 + IAM + Docker)
- [ ] **Improve eval framework** — relax retrieval matching to fuzzy/semantic match instead of exact string, expand test set beyond 20 queries
- [ ] **Improve intent classifier** — add more training data, expand math keyword shortcuts for formula-related queries
- [ ] **Scrape more data** — expand corpus beyond Cool Cosmos and NASA Imagine; add data from NASA Science, ESA, and astronomy textbooks
- [ ] **FastAPI web server** — `api_server.py` REST API
- [ ] **Frontend UI** — interactive web interface for the chatbot
- [ ] **Migrate to Amazon OpenSearch** — swap ChromaDB for managed vector DB when corpus exceeds ~10K chunks
- [ ] **Obsidian knowledge base integration** — ingest structured Obsidian vaults as an additional knowledge source for RAG
- [ ] **LoRA fine-tuning** — fine-tune a small open-source LLM (Llama/Mistral) on the astronomy corpus for offline inference
- [ ] **CI/CD pipeline** — automated eval runs on push, deploy on merge to main

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
