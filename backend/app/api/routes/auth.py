from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import AuthTokenResponse, CurrentUserResponse, LoginRequest, LogoutResponse, RegisterRequest
from app.services.auth_service import login_user, register_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthTokenResponse)
def register_endpoint(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    return register_user(db, payload)


@router.post("/login", response_model=AuthTokenResponse)
def login_endpoint(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    return login_user(db, payload)


@router.get("/me", response_model=CurrentUserResponse)
def me_endpoint(current_user: User = Depends(get_current_user)) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        status=current_user.status,
        created_at=current_user.created_at,
    )


@router.post("/logout", response_model=LogoutResponse)
def logout_endpoint() -> LogoutResponse:
    return LogoutResponse(success=True)
