#!/usr/bin/env python3
"""Admin CLI for reviewing pending corpus submissions.

Run from repo root:
    python scripts/review_pending.py

Approving an entry promotes it to data/astronomy_corpus.yml AND embeds it
into ChromaDB (uses bot_controller.save_to_corpus). Rejecting just marks
the entry status; nothing else changes.
"""
import os
import sys

# Make src/ importable so save_to_corpus loads cleanly.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)

from api.pending import get_entry, list_pending, update_status  # noqa: E402


def _print_entry(i: int, entry: dict) -> None:
    print(f"\n[{i}]  id: {entry['id']}    created: {entry['created_at']}")
    print(f"     Q: {entry['question']}")
    answer = entry["answer"]
    snippet = answer if len(answer) <= 400 else answer[:400] + "…"
    print(f"     A: {snippet}")


def _prompt_action() -> str:
    while True:
        choice = input("   approve (a) / reject (r) / skip (s) / quit (q): ").strip().lower()
        if choice in ("a", "r", "s", "q"):
            return choice
        print("   please enter a, r, s, or q.")


def _approve(entry: dict) -> bool:
    try:
        from bot_controller import save_to_corpus  # type: ignore
    except ImportError as e:
        print(f"   ERROR: could not import save_to_corpus ({e}).")
        print("   approval requires the full ML stack (torch/chroma/transformers).")
        return False
    try:
        save_to_corpus(entry["question"], entry["answer"])
    except Exception as e:
        print(f"   save_to_corpus failed: {e.__class__.__name__}: {e}")
        return False
    update_status(entry["id"], "approved")
    print(f"   approved and added to corpus + chroma")
    return True


def main() -> int:
    pending = list_pending()
    if not pending:
        print("no pending entries.")
        return 0

    print(f"{len(pending)} pending entries.")
    for i, entry in enumerate(pending, start=1):
        _print_entry(i, entry)
        action = _prompt_action()
        if action == "q":
            print("done.")
            return 0
        if action == "s":
            continue
        if action == "a":
            _approve(entry)
        elif action == "r":
            update_status(entry["id"], "rejected")
            print(f"   rejected")

    print("\nall pending entries reviewed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
