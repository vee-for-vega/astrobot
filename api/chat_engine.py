"""Tiered chat pipeline, callable. Wraps bot_controller.

Returns structured dicts with tier, similarity, sources, and token usage —
the API exposes these to the frontend so the CLI can render them."""
import os
import sys

# bot_controller lives in src/. PYTHONPATH set in the Dockerfile, but add it
# here too so the module imports cleanly under uvicorn-reload local dev.
SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

# Importing bot_controller triggers heavy model loads (DistilBERT, Chroma,
# sentence-transformers). Done once at process start.
from bot_controller import (  # type: ignore
    embedding_model,
    client,
    collection,
    retrieve_context,
    ANTHROPIC_MODEL,
    DIRECT_ANSWER_THRESHOLD,
    MAX_HISTORY_TURNS,
    MAX_TOKENS,
    RETRIEVAL_RELEVANCE_THRESHOLD,
    SYSTEM_PROMPT,
)

FALLBACK_THRESHOLD = 0.45  # for budget-exhausted Tier 1 fallback


class BudgetExhausted(Exception):
    """Raised when LLM budget is gone and no Tier 1 fallback exists."""


def _retrieve_top(question: str, n: int = 3) -> list[dict]:
    embedding = embedding_model.encode([question])[0].tolist()
    results = collection.query(
        query_embeddings=[embedding],
        n_results=n,
        include=["documents", "metadatas", "distances"],
    )
    out = []
    for i in range(len(results["documents"][0])):
        out.append({
            "doc": results["documents"][0][i],
            "meta": results["metadatas"][0][i],
            "similarity": round(1 - results["distances"][0][i], 4),
        })
    return out


def _extract_answer(hit: dict) -> str:
    if "answer_full" in hit["meta"]:
        return hit["meta"]["answer_full"]
    doc = hit["doc"]
    if "\nA: " in doc:
        return doc.split("\nA: ", 1)[1]
    return doc


def chat_once(question: str, history: list[dict] | None = None,
              llm_disabled: bool = False) -> dict:
    history = history or []
    hits = _retrieve_top(question, n=3)
    sources = [
        {"question": h["meta"].get("question", ""), "similarity": h["similarity"]}
        for h in hits
    ]
    top = hits[0] if hits else None
    top_sim = top["similarity"] if top else 0.0

    # Tier 1: high-similarity corpus match. No LLM call.
    if top and top_sim >= DIRECT_ANSWER_THRESHOLD:
        return {
            "answer": _extract_answer(top),
            "tier": 1,
            "similarity": top_sim,
            "sources": sources,
            "tokens": None,
            "fallback": False,
        }

    # Budget exhausted: try a looser Tier 1 lookup, else error.
    if llm_disabled:
        if top and top_sim >= FALLBACK_THRESHOLD:
            return {
                "answer": _extract_answer(top),
                "tier": 1,
                "similarity": top_sim,
                "sources": sources,
                "tokens": None,
                "fallback": True,
            }
        raise BudgetExhausted(
            "Daily LLM budget exhausted and no cached answer matches your question. "
            "Try asking about planets, stars, black holes, or NASA missions."
        )

    # Tier 2 / 3: full LLM call.
    context_str, _ = retrieve_context(question)
    chunks_used = sum(
        1 for h in hits if h["similarity"] >= RETRIEVAL_RELEVANCE_THRESHOLD
    )
    tier = 2 if chunks_used > 0 else 3

    augmented = (
        f"{context_str}\n\nUSER QUESTION: {question}" if context_str else question
    )
    messages = list(history)
    messages.append({"role": "user", "content": augmented})
    if len(messages) > MAX_HISTORY_TURNS * 2:
        messages = messages[-(MAX_HISTORY_TURNS * 2):]

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    return {
        "answer": response.content[0].text,
        "tier": tier,
        "similarity": top_sim,
        "sources": sources,
        "tokens": {
            "input": response.usage.input_tokens,
            "output": response.usage.output_tokens,
        },
        "fallback": False,
    }
