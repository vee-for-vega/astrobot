# LOCKED — acceptance criteria for tiered routing, frozen 2026-06-10.
# Owner of these criteria: architect (human). Changes go through a new
# architect task, never by the implementing agent.
#
# api/chat_engine.py::chat_once routing order: trajectory fast path ->
# Tier 1 corpus-direct -> budget-exhausted fallback -> Tier 2/3 LLM.
# The cost design these tests protect: the trajectory path and Tier 1
# make ZERO LLM calls. Tests fake bot_controller before import so no
# torch/Chroma/network is ever touched.

import sys
import types

import pytest


class _Vec:
    def tolist(self):
        return [0.0] * 8


class _FakeEmbedder:
    def encode(self, texts):
        return [_Vec() for _ in texts]


class _FakeAnthropic:
    """Records every messages.create call; returns a canned completion."""

    def __init__(self):
        self.calls = []
        outer = self

        class _Messages:
            def create(self, **kwargs):
                outer.calls.append(kwargs)
                return types.SimpleNamespace(
                    content=[types.SimpleNamespace(text="LLM ANSWER")],
                    usage=types.SimpleNamespace(input_tokens=11, output_tokens=7),
                )

        self.messages = _Messages()


class _FakeCollection:
    """Chroma stand-in. set_top() controls the best hit's similarity."""

    _EMPTY = {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    def __init__(self):
        self.next_results = dict(self._EMPTY)

    def set_top(self, similarity, question="how hot is mercury?", answer="Very hot."):
        self.next_results = {
            "documents": [[f"Q: {question}\nA: {answer}"]],
            "metadatas": [[{"question": question, "answer_full": answer}]],
            "distances": [[round(1.0 - similarity, 6)]],
        }

    def clear(self):
        self.next_results = dict(self._EMPTY)

    def query(self, **kwargs):
        return self.next_results


# Fake bot_controller must exist in sys.modules BEFORE api.chat_engine is
# imported — importing the real one loads DistilBERT + Chroma + creates a
# real Anthropic client.
_fake = types.ModuleType("bot_controller")
_fake.embedding_model = _FakeEmbedder()
_fake.client = _FakeAnthropic()
_fake.collection = _FakeCollection()
_fake.predict_intent = lambda q: ("define_concept", 0.99)
_fake.retrieve_context = lambda q: ("CONTEXT BLOCK", [])
_fake.save_to_corpus = lambda *a, **k: None
_fake.ANTHROPIC_MODEL = "claude-test"
_fake.DIRECT_ANSWER_THRESHOLD = 0.65
_fake.MAX_HISTORY_TURNS = 6
_fake.MAX_TOKENS = 400
_fake.RETRIEVAL_RELEVANCE_THRESHOLD = 0.30
_fake.SYSTEM_PROMPT = "test system prompt"
sys.modules["bot_controller"] = _fake

from api import chat_engine  # noqa: E402  (must follow the fake injection)


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    _fake.client.calls.clear()
    _fake.collection.clear()
    # Tier 2/3 auto-stages for review — never write the real pending queue.
    monkeypatch.setattr(chat_engine, "append_pending", lambda q, a: ("test-id", True))
    yield


def test_trajectory_question_short_circuits_with_zero_llm_calls():
    r = chat_engine.chat_once("show me the orbit of Mars")
    assert r["trajectory"]["planet"] == "Mars"
    assert r["tokens"] is None
    assert _fake.client.calls == []


def test_tier1_corpus_hit_answers_directly_with_zero_llm_calls():
    _fake.collection.set_top(0.90)
    r = chat_engine.chat_once("how hot is mercury?")
    assert r["tier"] == 1
    assert r["answer"] == "Very hot."
    assert r["fallback"] is False
    assert r["tokens"] is None
    assert _fake.client.calls == []


def test_tier2_uses_llm_with_retrieved_context():
    _fake.collection.set_top(0.50)  # between 0.30 and 0.65
    r = chat_engine.chat_once("what is a magnetar made of?")
    assert r["tier"] == 2
    assert r["answer"] == "LLM ANSWER"
    assert r["tokens"] == {"input": 11, "output": 7}
    assert len(_fake.client.calls) == 1
    # The call must carry bot_controller's canonical config, not literals.
    call = _fake.client.calls[0]
    assert call["model"] == _fake.ANTHROPIC_MODEL
    assert call["system"] == _fake.SYSTEM_PROMPT


def test_tier3_low_similarity_uses_llm_without_corpus_support():
    _fake.collection.set_top(0.10)  # below relevance threshold
    r = chat_engine.chat_once("what did you think of the game last night?")
    assert r["tier"] == 3
    assert len(_fake.client.calls) == 1


def test_budget_exhausted_falls_back_to_looser_corpus_match():
    _fake.collection.set_top(0.50)  # >= FALLBACK_THRESHOLD (0.45)
    r = chat_engine.chat_once("how hot is mercury?", llm_disabled=True)
    assert r["tier"] == 1
    assert r["fallback"] is True
    assert r["answer"] == "Very hot."
    assert _fake.client.calls == []


def test_budget_exhausted_with_no_match_raises_instead_of_calling_llm():
    _fake.collection.set_top(0.20)  # below FALLBACK_THRESHOLD
    with pytest.raises(chat_engine.BudgetExhausted):
        chat_engine.chat_once("how hot is mercury?", llm_disabled=True)
    assert _fake.client.calls == []
