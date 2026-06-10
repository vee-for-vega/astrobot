# LOCKED — acceptance criteria for the trajectory fast path, frozen 2026-06-10.
# Owner of these criteria: architect (human). Changes go through a new
# architect task, never by the implementing agent.
#
# api/trajectory.py is the deterministic zero-LLM branch: orbit questions
# must short-circuit before any model call and return a structured payload
# the frontend renders as an OrbitCard.

from api.trajectory import detect_planet, maybe_trajectory_response


def test_non_orbit_question_returns_none():
    # None hands control back to the tiered pipeline.
    assert maybe_trajectory_response("How hot is Venus?") is None
    assert maybe_trajectory_response("Who was the first person on the Moon?") is None


def test_orbit_question_returns_zero_token_trajectory_payload():
    r = maybe_trajectory_response("Show me the orbit of Mars")
    assert r is not None
    assert r["tokens"] is None  # the cost invariant: no LLM involved
    assert r["tier"] == 1
    assert r["trajectory"]["planet"] == "Mars"
    elements = r["trajectory"]["elements"]
    # Pin physical sanity, not exact catalog values: Mars semi-major axis
    # is ~1.524 AU, eccentricity ~0.093, inclination ~1.85 deg.
    assert 1.4 < elements["a"] < 1.6
    assert 0.0 < elements["e"] < 0.2
    assert 0.0 < elements["i"] < 4.0


def test_typo_resolves_via_fuzzy_match():
    planet, was_fuzzy = detect_planet("show me marz orbit")
    assert planet == "Mars"
    assert was_fuzzy is True


def test_possessive_and_plural_forms_resolve():
    assert detect_planet("show me Mars's orbit")[0] == "Mars"
    assert detect_planet("show earths orbit")[0] == "Earth"


def test_fuzzy_match_is_flagged_in_the_answer():
    r = maybe_trajectory_response("show me the orbit of jupitor")
    assert r is not None
    assert r["trajectory"]["planet"] == "Jupiter"
    # Fuzzy hits must be transparent to the user.
    assert "assume you meant" in r["answer"].lower()


def test_orbit_ask_without_planet_lists_the_options():
    r = maybe_trajectory_response("show me an orbit")
    assert r is not None
    assert r.get("trajectory") is None  # no card to render
    assert r["tokens"] is None  # still zero LLM cost
    assert "couldn't tell which planet" in r["answer"]
