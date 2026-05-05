"""JWT auth: shared password in, signed token out. HS256."""
import os
import time
import secrets
from typing import Optional

import jwt
from fastapi import Header, HTTPException

JWT_ALGO = "HS256"
JWT_TTL_SECONDS = 3600  # 1 hour

# Loaded from env at startup. Container won't start without these.
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "")
JWT_SIGNING_KEY = os.environ.get("JWT_SIGNING_KEY", "")


def issue_token(subject: str = "demo-user") -> dict:
    if not JWT_SIGNING_KEY:
        raise RuntimeError("JWT_SIGNING_KEY not set")
    now = int(time.time())
    jti = secrets.token_urlsafe(8)
    payload = {
        "sub": subject,
        "jti": jti,
        "iat": now,
        "exp": now + JWT_TTL_SECONDS,
    }
    token = jwt.encode(payload, JWT_SIGNING_KEY, algorithm=JWT_ALGO)
    return {"token": token, "expires_in": JWT_TTL_SECONDS, "jti": jti}


def verify_password(password: str) -> bool:
    if not AUTH_PASSWORD:
        raise RuntimeError("AUTH_PASSWORD not set")
    # secrets.compare_digest is timing-safe
    return secrets.compare_digest(password, AUTH_PASSWORD)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SIGNING_KEY, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid token")


def require_token(authorization: Optional[str] = Header(None)) -> dict:
    """FastAPI dependency. Use as: payload = Depends(require_token)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    return decode_token(token)
