"""Pending-corpus staging area.

Approved knowledge eventually lands in data/astronomy_corpus.yml + ChromaDB.
Before that, every /api/save submission goes through here so an admin can
review it. Pending entries are NOT retrievable in chat — they sit dormant
until reviewed via scripts/review_pending.py.
"""
import os
import secrets
from datetime import datetime, timezone
from typing import Optional

import yaml

PENDING_PATH = os.environ.get(
    "PENDING_CORPUS_PATH",
    os.path.join(os.path.dirname(__file__), "..", "data", "pending_corpus.yml"),
)


def _load() -> dict:
    if os.path.exists(PENDING_PATH):
        with open(PENDING_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {"entries": []}
    return {"entries": []}


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(PENDING_PATH), exist_ok=True)
    with open(PENDING_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, width=10000)


def append_pending(question: str, answer: str) -> tuple[str, bool]:
    """Stage a Q&A for admin approval.

    Returns (entry_id, was_new). Duplicates (same question, status=pending)
    return the existing entry's id without creating a new one."""
    data = _load()
    q_lower = question.strip().lower()
    for entry in data["entries"]:
        if (
            entry.get("status") == "pending"
            and entry.get("question", "").strip().lower() == q_lower
        ):
            return entry["id"], False

    entry_id = secrets.token_urlsafe(8)
    data["entries"].append(
        {
            "id": entry_id,
            "question": question.strip(),
            "answer": answer.strip(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
        }
    )
    _save(data)
    return entry_id, True


def list_pending() -> list[dict]:
    return [e for e in _load()["entries"] if e.get("status") == "pending"]


def get_entry(entry_id: str) -> Optional[dict]:
    for e in _load()["entries"]:
        if e["id"] == entry_id:
            return e
    return None


def update_status(entry_id: str, new_status: str) -> Optional[dict]:
    """Mark an entry approved/rejected. Returns the updated entry, or None."""
    if new_status not in ("approved", "rejected"):
        raise ValueError(f"invalid status: {new_status}")
    data = _load()
    for entry in data["entries"]:
        if entry["id"] == entry_id:
            entry["status"] = new_status
            entry["reviewed_at"] = datetime.now(timezone.utc).isoformat()
            _save(data)
            return entry
    return None
