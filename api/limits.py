"""In-memory rate limit (per JWT id) and daily token-budget tracker.

State is process-local. Resets when the container restarts. Fine for a
single-instance demo. Swap for DynamoDB if we ever scale out."""
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from threading import Lock

# Per-JWT sliding window
RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", "30"))
RATE_LIMIT_WINDOW_SECS = int(os.environ.get("RATE_LIMIT_WINDOW_SECS", "3600"))

# Daily Anthropic spend cap (USD)
DAILY_BUDGET_USD = float(os.environ.get("DAILY_BUDGET_USD", "1.00"))

# Sonnet 4.6 pricing per million tokens
INPUT_PRICE_PER_MTOK = 3.00
OUTPUT_PRICE_PER_MTOK = 15.00


# ---------- rate limit ----------

_rate_buckets: dict[str, deque] = defaultdict(deque)
_rate_lock = Lock()


def check_rate_limit(jti: str) -> tuple[bool, int]:
    """Returns (allowed, retry_after_seconds)."""
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW_SECS
    with _rate_lock:
        bucket = _rate_buckets[jti]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT_REQUESTS:
            retry = int(bucket[0] + RATE_LIMIT_WINDOW_SECS - now) + 1
            return False, retry
        bucket.append(now)
        return True, 0


# ---------- budget ----------

_budget_state = {"date": None, "spent_usd": 0.0}
_budget_lock = Lock()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _maybe_reset() -> None:
    today = _today()
    if _budget_state["date"] != today:
        _budget_state["date"] = today
        _budget_state["spent_usd"] = 0.0


def budget_remaining_usd() -> float:
    with _budget_lock:
        _maybe_reset()
        return max(0.0, DAILY_BUDGET_USD - _budget_state["spent_usd"])


def llm_disabled() -> bool:
    return budget_remaining_usd() <= 0.0


def record_usage(input_tokens: int, output_tokens: int) -> float:
    """Returns USD cost recorded."""
    cost = (
        input_tokens * INPUT_PRICE_PER_MTOK / 1_000_000
        + output_tokens * OUTPUT_PRICE_PER_MTOK / 1_000_000
    )
    with _budget_lock:
        _maybe_reset()
        _budget_state["spent_usd"] += cost
    return cost


def stats() -> dict:
    with _budget_lock:
        _maybe_reset()
        spent = _budget_state["spent_usd"]
    return {
        "daily_budget_usd": DAILY_BUDGET_USD,
        "spent_usd": round(spent, 4),
        "remaining_usd": round(max(0.0, DAILY_BUDGET_USD - spent), 4),
        "llm_disabled": spent >= DAILY_BUDGET_USD,
        "rate_limit": {
            "requests_per_window": RATE_LIMIT_REQUESTS,
            "window_secs": RATE_LIMIT_WINDOW_SECS,
        },
    }
