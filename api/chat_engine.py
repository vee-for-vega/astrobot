"""Tiered chat pipeline, callable. Wraps bot_controller.

Returns structured dicts with tier, similarity, sources, and token usage —
the API exposes these to the frontend so the CLI can render them."""
import logging
import os
import sys

logger = logging.getLogger("astrobot.chat_engine")

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
    predict_intent,
    retrieve_context,
    save_to_corpus,
    ANTHROPIC_MODEL,
    DIRECT_ANSWER_THRESHOLD,
    MAX_HISTORY_TURNS,
    MAX_TOKENS,
    RETRIEVAL_RELEVANCE_THRESHOLD,
    SYSTEM_PROMPT,
)
from api.pending import append_pending
from api.save_guard import ValidationError, validate as validate_for_save
from api.trajectory import maybe_trajectory_response

__all__ = [
    "BudgetExhausted",
    "chat_once",
    "client",
    "predict_intent",
    "save_to_corpus",
]


def _auto_submit_for_review(question: str, answer: str) -> None:
    """Best-effort: stage a Tier 2/3 Q&A for admin review.

    Runs the structural + intent guards (Layers 1 and 2) but skips the LLM
    judge — the human review is the final gate, so a per-question Claude
    call would just be cost without value. Silent on any failure.
    """
    try:
        intent_label, _ = predict_intent(question)
    except Exception:
        intent_label = None
    try:
        validate_for_save(question, answer, intent_label=intent_label)
    except ValidationError as e:
        logger.info("auto-submit rejected: %s", e.reason)
        return
    try:
        append_pending(question, answer)
    except Exception:
        logger.exception("auto-submit append_pending failed")

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

    # Trajectory fast path. Deterministic, no LLM call, returns a structured
    # payload the frontend renders as an animated OrbitCard.
    traj = maybe_trajectory_response(question)
    if traj is not None:
        return traj

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
    answer_text = response.content[0].text

    # Auto-stage for admin review. Pending entries are not retrieved in chat;
    # they live in data/pending_corpus.yml until scripts/review_pending.py runs.
    _auto_submit_for_review(question, answer_text)

    return {
        "answer": answer_text,
        "tier": tier,
        "similarity": top_sim,
        "sources": sources,
        "tokens": {
            "input": response.usage.input_tokens,
            "output": response.usage.output_tokens,
        },
        "fallback": False,
    }
