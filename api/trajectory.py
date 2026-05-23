"""Trajectory fast path. If a question is asking to see a planet's orbit,
we skip the LLM entirely and return a structured payload the frontend
renders as an OrbitCard."""
import difflib
import os
import re

import yaml

ORBITAL_ELEMENTS_PATH = os.environ.get(
    "ORBITAL_ELEMENTS_PATH",
    os.path.join(os.path.dirname(__file__), "..", "data", "orbital_elements.yml"),
)

TRAJECTORY_KEYWORDS = ("trajectory", "orbit", "orbital path", "ellipse")
FUZZY_CUTOFF = 0.75
MIN_TOKEN_LEN = 3

with open(ORBITAL_ELEMENTS_PATH) as f:
    _DATA = yaml.safe_load(f)

_PLANETS_BY_NAME = {p["name"].lower(): p for p in _DATA["planets"]}
_STAR = _DATA["star"]
_PLANET_LIST = list(_PLANETS_BY_NAME.keys())

_PLANET_REGEX = re.compile(
    r"\b(" + "|".join(re.escape(n) for n in _PLANETS_BY_NAME) + r")(?:'?s)?\b",
    re.IGNORECASE,
)
_TOKEN_REGEX = re.compile(r"[a-zA-Z]+")


def is_trajectory_question(question: str) -> bool:
    ql = question.lower()
    return any(k in ql for k in TRAJECTORY_KEYWORDS)


def detect_planet(question: str) -> tuple[str | None, bool]:
    """Returns (planet_name, was_fuzzy). Exact match first, then difflib
    fallback for typos like 'marz' / 'jupitor' / 'erth'."""
    m = _PLANET_REGEX.search(question)
    if m:
        return m.group(1).capitalize(), False

    for token in _TOKEN_REGEX.findall(question.lower()):
        if len(token) < MIN_TOKEN_LEN:
            continue
        # Try the raw token and a singularized form (drop trailing s).
        for candidate in (token, token.rstrip("s")):
            matches = difflib.get_close_matches(
                candidate, _PLANET_LIST, n=1, cutoff=FUZZY_CUTOFF
            )
            if matches:
                return matches[0].capitalize(), True

    return None, False


def build_trajectory_payload(planet: str) -> dict | None:
    p = _PLANETS_BY_NAME.get(planet.lower())
    if not p:
        return None
    return {
        "planet": p["name"],
        "star": {"name": _STAR["name"], "mass": _STAR["mass"]},
        "elements": {
            "a": p["a"],
            "e": p["e"],
            "i": p["i"],
            "period": p.get("period"),
            "M0": p.get("M0"),
        },
    }


def _no_planet_response() -> dict:
    names = ", ".join(p["name"] for p in _DATA["planets"])
    return {
        "answer": (
            "I couldn't tell which planet you meant. "
            f"I can show the orbit for any of these: {names}. "
            "Try 'show me Mars's orbit'."
        ),
        "tier": 1,
        "similarity": 1.0,
        "sources": [],
        "tokens": None,
        "fallback": False,
    }


def maybe_trajectory_response(question: str) -> dict | None:
    if not is_trajectory_question(question):
        return None

    planet, was_fuzzy = detect_planet(question)
    if not planet:
        return _no_planet_response()

    payload = build_trajectory_payload(planet)
    if not payload:
        return None

    e = payload["elements"]
    period_d = e.get("period") or 0.0
    period_label = (
        f"{period_d:.1f} days" if period_d < 365 else f"{period_d / 365.25:.2f} years"
    )
    lead = (
        f"I'll assume you meant {payload['planet']}. "
        if was_fuzzy
        else f"Here's the trajectory of {payload['planet']}. "
    )
    answer = (
        lead
        + f"It orbits at a semi-major axis of {e['a']:.3f} AU with an eccentricity of "
        f"{e['e']:.4f} and an inclination of {e['i']:.2f}° relative to the ecliptic. "
        f"One full orbit takes about {period_label}."
    )
    return {
        "answer": answer,
        "tier": 1,
        "similarity": 1.0,
        "sources": [],
        "tokens": None,
        "fallback": False,
        "trajectory": payload,
    }
