"""
auth.py - simple token auth with stdlib password hashing
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import AccessToken, User

security = HTTPBearer(auto_error=False)


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algo, salt, digest = stored_hash.split("$", 2)
        if algo != "pbkdf2_sha256":
            return False
        candidate = hash_password(password, salt).split("$", 2)[2]
        return hmac.compare_digest(candidate, digest)
    except ValueError:
        return False


def make_token() -> str:
    return secrets.token_urlsafe(48)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please log in first.")

    result = await db.execute(
        select(AccessToken).where(AccessToken.token == credentials.credentials)
    )
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired. Please log in again.")

    user = await db.get(User, token.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return user
