"""
routers/auth.py - registration, login, logout, and current user
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import hash_password, make_token, verify_password, get_current_user
from database import get_db
from models import AccessToken, User
from schemas import AuthResponse, UserCreate, UserLogin, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    email = payload.email.lower().strip()
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This email is already registered.")

    user = User(
        full_name=payload.full_name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.flush()

    token_value = make_token()
    db.add(AccessToken(user_id=user.id, token=token_value))
    await db.commit()
    await db.refresh(user)
    return AuthResponse(token=token_value, user=UserOut.model_validate(user))


@router.post("/login", response_model=AuthResponse)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    email = payload.email.lower().strip()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong email or password.")

    token_value = make_token()
    db.add(AccessToken(user_id=user.id, token=token_value))
    await db.commit()
    await db.refresh(user)
    return AuthResponse(token=token_value, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout", status_code=204)
async def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    if credentials:
        result = await db.execute(select(AccessToken).where(AccessToken.token == credentials.credentials))
        token = result.scalar_one_or_none()
        if token:
            await db.delete(token)
            await db.commit()
