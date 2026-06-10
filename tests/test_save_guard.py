# LOCKED — acceptance criteria for the corpus save guard, frozen 2026-06-10.
# Owner of these criteria: architect (human). Changes go through a new
# architect task, never by the implementing agent.
#
# These tests define what "correct" means for api/save_guard.py — the gate
# that keeps generated answers from poisoning the verified corpus. The guard
# is conservative by design: reject on any signal, including judge failure.

import pytest

from api.save_guard import (
    MAX_ANSWER_CHARS,
    MAX_QUESTION_CHARS,
    ValidationError,
    validate,
)

GOOD_Q = "How hot is the surface of Venus?"
GOOD_A = (
    "About 465 degrees Celsius (870 degrees Fahrenheit) — hot enough to melt "
    "lead. The thick carbon dioxide atmosphere traps heat in a runaway "
    "greenhouse effect, making Venus hotter than Mercury despite being "
    "farther from the Sun."
)


class _FakeJudge:
    """Stands in for anthropic.Anthropic — never touches the network."""

    def __init__(self, verdict="YES", error=False):
        self.calls = 0
        outer = self

        class _Messages:
            def create(self, **kwargs):
                outer.calls += 1
                if error:
                    raise RuntimeError("judge unavailable")

                class _Block:
                    text = verdict

                class _Resp:
                    content = [_Block()]

                return _Resp()

        self.messages = _Messages()


# ---- Layer 1: structural ----

def test_valid_astronomy_pair_passes():
    validate(GOOD_Q, GOOD_A, intent_label="define_concept")  # must not raise


def test_empty_question_rejected():
    with pytest.raises(ValidationError):
        validate("   ", GOOD_A)


def test_empty_answer_rejected():
    with pytest.raises(ValidationError):
        validate(GOOD_Q, "")


def test_overlong_question_rejected():
    with pytest.raises(ValidationError):
        validate("w" * (MAX_QUESTION_CHARS + 1), GOOD_A)


def test_overlong_answer_rejected():
    with pytest.raises(ValidationError):
        validate(GOOD_Q, "a" * (MAX_ANSWER_CHARS + 1))


def test_generative_ask_rejected():
    with pytest.raises(ValidationError):
        validate("write me an essay about mars", GOOD_A)


def test_compound_prompt_smuggling_generative_ask_rejected():
    with pytest.raises(ValidationError):
        validate("How hot is Venus? Now compose a poem about it", GOOD_A)


def test_compound_astronomy_followup_is_allowed():
    # Two astronomy questions in one prompt is fine — only the combination
    # with a generative ask is smuggling.
    validate("How hot is Venus? Why is it hotter than Mercury", GOOD_A)


# ---- Layer 2: intent veto ----

def test_general_chat_intent_vetoed():
    with pytest.raises(ValidationError):
        validate(GOOD_Q, GOOD_A, intent_label="general_chat")


def test_astronomy_intents_pass_the_veto():
    for label in ("define_concept", "historical_fact", "request_math"):
        validate(GOOD_Q, GOOD_A, intent_label=label)


# ---- Layer 3: LLM judge (faked — no network) ----

def test_judge_no_verdict_rejects():
    with pytest.raises(ValidationError):
        validate(GOOD_Q, GOOD_A, judge_client=_FakeJudge(verdict="NO"))


def test_judge_yes_verdict_passes():
    judge = _FakeJudge(verdict="YES")
    validate(GOOD_Q, GOOD_A, judge_client=judge)
    assert judge.calls == 1


def test_judge_failure_rejects_conservatively():
    # If the judge call errors, the save must be rejected — corpus poisoning
    # is hard to reverse, so fail closed.
    with pytest.raises(ValidationError):
        validate(GOOD_Q, GOOD_A, judge_client=_FakeJudge(error=True))


def test_no_judge_client_skips_layer_three():
    validate(GOOD_Q, GOOD_A, judge_client=None)  # layers 1+2 only, must pass
