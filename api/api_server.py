"""FastAPI app for the AstroBot demo.

Endpoints:
  GET  /api/health   — liveness check, no auth
  POST /api/login    — exchange shared password for a 1h JWT
  POST /api/chat     — auth required, runs the tiered pipeline
  GET  /api/stats    — auth required, current budget + rate-limit state
"""
import logging
import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api import auth, limits
from api.chat_engine import BudgetExhausted, chat_once

logger = logging.getLogger("astrobot.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="AstroBot API", version="0.1.0")

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

class LoginRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=200)


class LoginResponse(BaseModel):
    token: str
    expires_in: int


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


# ---------- endpoints ----------

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/login", response_model=LoginResponse)
def login(req: LoginRequest) -> LoginResponse:
    if not auth.verify_password(req.password):
        raise HTTPException(status_code=401, detail="invalid password")
    issued = auth.issue_token()
    return LoginResponse(token=issued["token"], expires_in=issued["expires_in"])


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest, payload: dict = Depends(auth.require_token)) -> ChatResponse:
    jti = payload.get("jti", "anon")

    allowed, retry = limits.check_rate_limit(jti)
    if not allowed:
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

    return ChatResponse(
        answer=result["answer"],
        tier=result["tier"],
        similarity=result["similarity"],
        sources=result["sources"],
        fallback=result["fallback"],
        tokens=result.get("tokens"),
        cost_usd=cost,
    )


@app.get("/api/stats")
def stats(payload: dict = Depends(auth.require_token)) -> dict:
    return limits.stats()
