from __future__ import annotations

from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User
from app.schemas.auth import AuthTokenResponse, CurrentUserResponse, LoginRequest, RegisterRequest


def _to_current_user_response(user: User) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        created_at=user.created_at,
    )


def register_user(db: Session, payload: RegisterRequest) -> AuthTokenResponse:
    existing = db.scalars(select(User).where(User.email == payload.email)).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已注册。")

    user = User(
        id=f"user-{uuid4().hex}",
        email=str(payload.email),
        display_name=payload.display_name.strip(),
        password_hash=get_password_hash(payload.password),
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return AuthTokenResponse(
        access_token=create_access_token(subject=user.id, email=user.email),
        user=_to_current_user_response(user),
    )


def login_user(db: Session, payload: LoginRequest) -> AuthTokenResponse:
    user = db.scalars(select(User).where(User.email == payload.email)).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误。")
    return AuthTokenResponse(
        access_token=create_access_token(subject=user.id, email=user.email),
        user=_to_current_user_response(user),
    )
