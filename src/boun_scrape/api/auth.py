import time
import hmac
import hashlib
import base64
import json
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from boun_scrape.config import Settings, get_settings

JWT_ALG = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

def _b64_decode(data: str) -> bytes:
    padding = 4 - (len(data) % 4)
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data.encode("ascii"))

def create_jwt_token(payload: dict, secret_key: str, expires_delta: timedelta | None = None) -> str:
    header = {"alg": JWT_ALG, "typ": "JWT"}
    to_encode = payload.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=1)
    to_encode["exp"] = int(expire.timestamp())
    to_encode["iat"] = int(now.timestamp())

    header_b64 = _b64_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64_encode(json.dumps(to_encode, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    
    signature = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64_encode(signature)
    return f"{header_b64}.{payload_b64}.{sig_b64}"

def verify_jwt_token(token: str, secret_key: str) -> dict | None:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        header = json.loads(_b64_decode(header_b64).decode("utf-8"))
        if not isinstance(header, dict) or header.get("alg") != JWT_ALG:
            return None

        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual_sig = _b64_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        payload = json.loads(_b64_decode(payload_b64).decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        exp = payload.get("exp")
        if exp and int(time.time()) > exp:
            return None
        return payload
    except Exception:
        return None

def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verifies a plain password against a bcrypt hash. The only supported scheme."""
    if not plain_password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(plain_password.strip().encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # password_hash is not a valid bcrypt hash
        return False

async def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
) -> str:
    settings: Settings = request.app.state.settings if hasattr(request, "app") and hasattr(request.app.state, "settings") and request.app.state.settings is not None else get_settings()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = verify_jwt_token(token, settings.jwt_secret_key)
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload["sub"]
