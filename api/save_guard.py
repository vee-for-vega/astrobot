"""Three-layer guard for /api/save.

Layer 1 — structural: length caps, compound-prompt detector.
Layer 2 — intent: reject anything classified as general_chat.
Layer 3 — llm judge: a cheap Claude call that vetoes off-topic answers.

Conservative on every layer — corpus poisoning is hard to reverse, so we
reject on any signal of trouble (including judge failures).
"""
import os
import re
from typing import Optional

import anthropic

MAX_QUESTION_CHARS = 300
MAX_ANSWER_CHARS = 4000

GENERATIVE_KEYWORDS = (
    "write me",
    "draft",
    "compose",
    "essay",
    "paper about",
    "page paper",
    "summarize",
    "summarise",
    "translate",
    "write code",
    "script",
    "poem",
    "story about",
    "letter",
    "email",
    "recipe",
)

# A question mark followed by ≥1 more word signals a second clause.
COMPOUND_PATTERN = re.compile(r"\?\s+\S")

JUDGE_MODEL = os.environ.get("SAVE_JUDGE_MODEL", "claude-haiku-4-5-20251001")


class ValidationError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _structural_check(question: str, answer: str) -> Optional[str]:
    if not question.strip() or not answer.strip():
        return "empty question or answer"
    if len(question) > MAX_QUESTION_CHARS:
        return f"question exceeds {MAX_QUESTION_CHARS} chars"
    if len(answer) > MAX_ANSWER_CHARS:
        return f"answer exceeds {MAX_ANSWER_CHARS} chars"
    ql = question.lower()
    has_compound = bool(COMPOUND_PATTERN.search(question))
    has_generative = any(k in ql for k in GENERATIVE_KEYWORDS)
    if has_compound and has_generative:
        return "compound prompt mixing astronomy with a generative ask"
    if has_generative:
        return "question contains a generative-content ask"
    return None


def _intent_check(intent_label: Optional[str]) -> Optional[str]:
    if intent_label == "general_chat":
        return "question classified as general chat (non-astronomy)"
    return None


def _judge_check(question: str, answer: str, client: anthropic.Anthropic) -> Optional[str]:
    prompt = (
        "You are a corpus moderator for an astronomy knowledge base.\n\n"
        f"QUESTION: {question}\n\nANSWER: {answer}\n\n"
        "Is this Q&A pair (a) on-topic for an astronomy/space knowledge base, "
        "(b) factually focused, and (c) free of essays, code, translations, "
        "or off-topic digressions? Reply with one word only: YES or NO."
    )
    try:
        resp = client.messages.create(
            model=JUDGE_MODEL,
            max_tokens=4,
            messages=[{"role": "user", "content": prompt}],
        )
        verdict = resp.content[0].text.strip().upper()
        if verdict.startswith("YES"):
            return None
        return f"judge rejected (verdict: {verdict[:8]})"
    except Exception as e:
        return f"judge call failed: {e.__class__.__name__}"


def validate(
    question: str,
    answer: str,
    *,
    intent_label: Optional[str] = None,
    judge_client: Optional[anthropic.Anthropic] = None,
) -> None:
    """Raise ValidationError if save should be rejected."""
    reason = _structural_check(question, answer)
    if reason:
        raise ValidationError(reason)

    reason = _intent_check(intent_label)
    if reason:
        raise ValidationError(reason)

    if judge_client is not None:
        reason = _judge_check(question, answer, judge_client)
        if reason:
            raise ValidationError(reason)
