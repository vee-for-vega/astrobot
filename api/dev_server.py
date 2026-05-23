"""Lightweight dev server for local UI testing.

Serves only the trajectory fast path — no auth, no RAG, no torch.
Useful when you want to verify the new web UI without installing the
full ML stack. Do NOT use in production.

Run: uvicorn api.dev_server:app --reload --port 8000
"""
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api.pending import append_pending
from api.save_guard import ValidationError, validate as validate_for_save
from api.trajectory import maybe_trajectory_response

app = FastAPI(title="AstroBot dev API", version="0.0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=200)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    history: list[dict] | None = None


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "mode": "dev"}


@app.post("/api/login")
def login(req: LoginRequest) -> dict:
    # Dev only: accept anything, issue a static token.
    _ = req.password
    return {"token": "dev-token", "expires_in": 60 * 60 * 24}


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict:
    traj = maybe_trajectory_response(req.question)
    if traj is not None:
        return traj
    answer = "(dev mode: RAG is disabled — ask about a planet's orbit or trajectory)"
    # Auto-submit even in dev so the pending flow is exercised end-to-end.
    try:
        validate_for_save(req.question, answer)
        append_pending(req.question, answer)
    except ValidationError:
        pass
    return {
        "answer": answer,
        "tier": 3,
        "similarity": 0.0,
        "sources": [],
        "tokens": None,
        "fallback": False,
        "trajectory": None,
    }


@app.get("/api/stats")
def stats() -> dict:
    return {
        "daily_budget_usd": 1.0,
        "spent_usd": 0.0,
        "remaining_usd": 1.0,
        "llm_disabled": True,
        "rate_limit": {"requests_per_window": 999, "window_secs": 60},
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
