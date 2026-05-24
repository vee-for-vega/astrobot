"""FastAPI app for the AstroBot demo.

Endpoints:
  GET  /api/health   — liveness check
  POST /api/chat     — runs the tiered pipeline; Tier 2/3 answers are
                      auto-submitted to data/pending_corpus.yml for admin
                      review via scripts/review_pending.py
  GET  /api/stats    — current budget + rate-limit state

No auth. Rate limit is per client IP (sliding window) and a hard daily
USD cap on Anthropic spend acts as the global abuse ceiling.
"""
import logging
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api import limits
from api.chat_engine import BudgetExhausted, chat_once

logger = logging.getLogger("astrobot.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="AstroBot API", version="0.2.0")

# Enable permissive CORS only for local dev. Prod request goes same-origin
# through CloudFront, so this is off by default.
if os.environ.get("ENABLE_CORS") == "1":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ---------- request / response models ----------

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    history: list[dict] | None = None


class ChatResponse(BaseModel):
    answer: str
    tier: int
    similarity: float
    sources: list[dict]
    fallback: bool
    tokens: dict | None = None
    cost_usd: float | None = None
    trajectory: dict | None = None


# ---------- helpers ----------

def _client_ip(request: Request) -> str:
    """Get the original client IP. Behind CloudFront, X-Forwarded-For
    carries the real IP at the front of a comma-separated list."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ---------- endpoints ----------

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request) -> ChatResponse:
    ip = _client_ip(request)

    # Pre-check rate limit. Free tiers don't increment the bucket — only
    # Claude-touching calls do (recorded after chat_once returns below).
    blocked, retry = limits.is_blocked(ip)
    if blocked:
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(retry)},
            content={"detail": f"rate limit exceeded; retry in {retry}s"},
        )

    try:
        result = chat_once(
            req.question,
            history=req.history,
            llm_disabled=limits.llm_disabled(),
        )
    except BudgetExhausted as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("chat failed")
        raise HTTPException(status_code=500, detail=f"chat failed: {e.__class__.__name__}")

    cost = None
    if result.get("tokens"):
        cost = limits.record_usage(
            result["tokens"]["input"], result["tokens"]["output"]
        )
        cost = round(cost, 6)
        # Only Claude-touching requests count against the per-IP rate limit.
        limits.record_request(ip)

    return ChatResponse(
        answer=result["answer"],
        tier=result["tier"],
        similarity=result["similarity"],
        sources=result["sources"],
        fallback=result["fallback"],
        tokens=result.get("tokens"),
        cost_usd=cost,
        trajectory=result.get("trajectory"),
    )


@app.get("/api/stats")
def stats() -> dict:
    return limits.stats()
