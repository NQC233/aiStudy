# Spec 18 Basic User System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first production-style user system with email/password login, bearer-token authentication, and user-scoped data isolation across the existing asset workflow.

**Architecture:** The implementation proceeds in four layers. First, add authentication primitives: password hashing, JWT issuance/verification, auth schemas, and auth routes. Second, replace the current fixed `local_dev_user_id` request identity with a unified `current_user` dependency and push `user_id` through service boundaries. Third, close all owner-check gaps so asset, reader, retrieval, chat, notes, slides, and async-entry routes always read by `(resource_id, user_id)` rather than primary key only. Fourth, add the minimal frontend auth loop: token persistence, bootstrap, guarded routes, login/register pages, top-level account shell, and real browser verification.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic Settings, PyJWT, Passlib bcrypt, Vue 3, Pinia, Vue Router, Playwright.

---

## File Structure

**Backend auth/config layer**
- Modify: `backend/app/core/config.py`
- Create: `backend/app/core/security.py`
- Modify: `backend/app/models/user.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/services/auth_service.py`
- Create: `backend/app/api/deps/auth.py`
- Create: `backend/app/api/routes/auth.py`
- Modify: `backend/app/api/router.py`
- Modify: `backend/pyproject.toml`
- Create: `backend/alembic/versions/<timestamp>_add_user_password_hash_and_auth_fields.py`

**Backend owner-check and route layer**
- Modify: `backend/app/api/routes/assets.py`
- Modify: `backend/app/api/routes/chat.py`
- Modify: `backend/app/api/routes/notes.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/__init__.py`
- Modify: `backend/app/services/asset_service.py`
- Modify: `backend/app/services/asset_create_service.py`
- Modify: `backend/app/services/asset_reader_service.py`
- Modify: `backend/app/services/retrieval_service.py`
- Modify: `backend/app/services/chat_service.py`
- Modify: `backend/app/services/note_service.py`
- Modify: `backend/app/services/document_parse_service.py`
- Modify: `backend/app/services/mindmap_service.py`
- Modify: `backend/app/services/slide_dsl_service.py`
- Modify: `backend/app/services/slide_generation_v2_service.py`
- Modify: `backend/app/services/slide_tts_service.py`

**Frontend auth layer**
- Modify: `frontend/src/main.ts`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/router/routes.ts`
- Modify: `frontend/src/api/assets.ts`
- Create: `frontend/src/api/auth.ts`
- Create: `frontend/src/stores/auth.ts`
- Create: `frontend/src/pages/auth/LoginPage.vue`
- Create: `frontend/src/pages/auth/RegisterPage.vue`
- Modify: `frontend/src/pages/workspace/WorkspacePage.vue`
- Modify: `frontend/src/components/PdfReaderPanel.vue`

**Tests**
- Create: `backend/tests/test_auth_service.py`
- Create: `backend/tests/test_auth_dependency.py`
- Create: `backend/tests/test_auth_routes.py`
- Create: `backend/tests/test_asset_user_isolation.py`
- Create: `backend/tests/test_chat_user_isolation.py`
- Create: `backend/tests/test_note_user_isolation.py`
- Create: `backend/tests/test_reader_user_isolation.py`
- Create: `backend/tests/test_slides_user_isolation.py`
- Create: `frontend/tests/e2e/spec18-auth.spec.ts`
- Modify: `frontend/tests/e2e/spec12-playback.spec.ts`
- Modify: `frontend/tests/e2e/spec12-docker-real.spec.ts`

**Docs/status**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `docs/checklist.md`
- Modify: `docs/specs/spec-18-basic-user-system.md`

---

### Task 1: Add password storage, auth config, and security primitives

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/models/user.py`
- Create: `backend/app/core/security.py`
- Create: `backend/tests/test_auth_service.py`
- Modify: `backend/tests/test_runtime_config.py`
- Create: `backend/alembic/versions/<timestamp>_add_user_password_hash_and_auth_fields.py`
- Test: `backend/tests/test_auth_service.py`
- Test: `backend/tests/test_runtime_config.py`

- [ ] **Step 1: Write the failing tests for auth config and security helpers**

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)


class AuthSecurityTests(unittest.TestCase):
    def test_settings_expose_auth_defaults(self) -> None:
        settings = Settings(
            auth_jwt_secret="test-secret",
            auth_access_token_expire_minutes=120,
        )

        self.assertEqual(settings.auth_jwt_secret, "test-secret")
        self.assertEqual(settings.auth_access_token_expire_minutes, 120)
        self.assertFalse(settings.auth_dev_bypass_enabled)

    def test_password_hash_round_trip(self) -> None:
        hashed = get_password_hash("paper-pass-123")

        self.assertNotEqual(hashed, "paper-pass-123")
        self.assertTrue(verify_password("paper-pass-123", hashed))
        self.assertFalse(verify_password("wrong-pass", hashed))

    def test_access_token_round_trip(self) -> None:
        token = create_access_token(subject="user-1", email="user@example.com")
        payload = decode_access_token(token)

        self.assertEqual(payload["sub"], "user-1")
        self.assertEqual(payload["email"], "user@example.com")
```

- [ ] **Step 2: Run the failing backend tests**

Run: `python -m unittest backend.tests.test_auth_service backend.tests.test_runtime_config -v`
Expected: FAIL with `ModuleNotFoundError` for `app.core.security` and missing auth settings fields.

- [ ] **Step 3: Add auth dependencies, settings, user password storage, and security helpers**

```toml
# backend/pyproject.toml
[project]
dependencies = [
  "alembic>=1.15.2",
  "celery[redis]>=5.4.0",
  "dashscope>=1.25.0",
  "fastapi>=0.110.0",
  "oss2>=2.19.1",
  "passlib[bcrypt]>=1.7.4",
  "pgvector>=0.3.6",
  "psycopg[binary]>=3.1.18",
  "pydantic-settings>=2.2.1",
  "PyJWT>=2.8.0",
  "python-multipart>=0.0.20",
  "sqlalchemy>=2.0.28",
  "uvicorn[standard]>=0.28.0",
]
```

```python
# backend/app/core/config.py
class Settings(BaseSettings):
    auth_jwt_secret: str = "change-me-in-env"
    auth_access_token_expire_minutes: int = 60 * 24 * 7
    auth_dev_bypass_enabled: bool = False
```

```python
# backend/app/models/user.py
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
```

```python
# backend/app/core/security.py
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    return pwd_context.verify(password, password_hash)


def create_access_token(*, subject: str, email: str) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.auth_access_token_expire_minutes)
    return jwt.encode(
        {"sub": subject, "email": email, "exp": expires_at},
        settings.auth_jwt_secret,
        algorithm="HS256",
    )


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.auth_jwt_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录态无效或已过期。") from exc
    if not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录态无效或已过期。")
    return payload
```

- [ ] **Step 4: Add the Alembic migration for `password_hash`**

```python
from alembic import op
import sqlalchemy as sa

revision = "20260425_0001"
down_revision = "20260304_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_hash")
```

- [ ] **Step 5: Run tests again**

Run: `python -m unittest backend.tests.test_auth_service backend.tests.test_runtime_config -v`
Expected: PASS with auth config and security helper tests green.

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/app/core/config.py backend/app/models/user.py backend/app/core/security.py backend/tests/test_auth_service.py backend/tests/test_runtime_config.py backend/alembic/versions
git commit -m "feat: add auth security primitives"
```

### Task 2: Add auth schemas, service layer, dependency, and auth routes

**Files:**
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/services/auth_service.py`
- Create: `backend/app/api/deps/auth.py`
- Create: `backend/app/api/routes/auth.py`
- Modify: `backend/app/api/router.py`
- Modify: `backend/app/services/__init__.py`
- Create: `backend/tests/test_auth_routes.py`
- Create: `backend/tests/test_auth_dependency.py`
- Test: `backend/tests/test_auth_routes.py`
- Test: `backend/tests/test_auth_dependency.py`

- [ ] **Step 1: Write the failing tests for register/login/me and bearer parsing**

```python
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import HTTPException

from app.api.deps.auth import resolve_bearer_token
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import register_user, login_user


class AuthRouteShapeTests(unittest.TestCase):
    def test_resolve_bearer_token_accepts_standard_header(self) -> None:
        token = resolve_bearer_token("Bearer abc.def.ghi")
        self.assertEqual(token, "abc.def.ghi")

    def test_resolve_bearer_token_rejects_missing_header(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            resolve_bearer_token(None)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_register_and_login_functions_exist(self) -> None:
        self.assertTrue(callable(register_user))
        self.assertTrue(callable(login_user))
        self.assertEqual(RegisterRequest(email="a@example.com", password="paper-pass-123", display_name="A").email, "a@example.com")
        self.assertEqual(LoginRequest(email="a@example.com", password="paper-pass-123").email, "a@example.com")
```

- [ ] **Step 2: Run the failing auth route tests**

Run: `python -m unittest backend.tests.test_auth_routes backend.tests.test_auth_dependency -v`
Expected: FAIL with missing `auth.py` schema/service/dependency modules.

- [ ] **Step 3: Add auth schemas and service methods**

```python
# backend/app/schemas/auth.py
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class CurrentUserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    status: str
    created_at: datetime


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: CurrentUserResponse


class LogoutResponse(BaseModel):
    success: bool
```

```python
# backend/app/services/auth_service.py
from __future__ import annotations

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
        id=f"user-{payload.email}",
        email=payload.email,
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
```

- [ ] **Step 4: Add auth dependency and routes, then wire router exports**

```python
# backend/app/api/deps/auth.py
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User


def resolve_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少有效的 Bearer Token。")
    return authorization.removeprefix("Bearer ").strip()


def get_current_user(
    db: Session = Depends(get_db),
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if settings.auth_dev_bypass_enabled:
        dev_user = db.get(User, settings.local_dev_user_id)
        if dev_user is not None:
            return dev_user
    token = resolve_bearer_token(authorization)
    payload = decode_access_token(token)
    user = db.get(User, payload["sub"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录态无效或已过期。")
    return user
```

```python
# backend/app/api/routes/auth.py
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
```

```python
# backend/app/api/router.py
from app.api.routes.auth import router as auth_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(assets_router)
api_router.include_router(chat_router)
api_router.include_router(notes_router)
```

- [ ] **Step 5: Run the auth route/dependency tests**

Run: `python -m unittest backend.tests.test_auth_routes backend.tests.test_auth_dependency -v`
Expected: PASS with route and dependency shape tests green.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/auth.py backend/app/services/auth_service.py backend/app/api/deps/auth.py backend/app/api/routes/auth.py backend/app/api/router.py backend/app/services/__init__.py backend/tests/test_auth_routes.py backend/tests/test_auth_dependency.py
git commit -m "feat: add auth api and current user dependency"
```

### Task 3: Replace fixed dev identity in route layer with `current_user`

**Files:**
- Modify: `backend/app/api/routes/assets.py`
- Modify: `backend/app/api/routes/chat.py`
- Modify: `backend/app/api/routes/notes.py`
- Modify: `backend/app/services/chat_service.py`
- Modify: `backend/app/services/note_service.py`
- Modify: `backend/app/services/asset_create_service.py`
- Create: `backend/tests/test_asset_user_isolation.py`
- Create: `backend/tests/test_chat_user_isolation.py`
- Create: `backend/tests/test_note_user_isolation.py`
- Test: `backend/tests/test_asset_user_isolation.py`
- Test: `backend/tests/test_chat_user_isolation.py`
- Test: `backend/tests/test_note_user_isolation.py`

- [ ] **Step 1: Write failing tests for route-to-service `user_id` propagation**

```python
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.routes.assets import create_asset_chat_session_endpoint, create_asset_note_endpoint, upload_asset_endpoint
from app.schemas.chat import ChatSessionCreateRequest
from app.schemas.note import CreateNoteRequest, NoteAnchorPayload


class RouteUserPropagationTests(unittest.TestCase):
    def test_chat_session_creation_uses_current_user_id(self) -> None:
        current_user = SimpleNamespace(id="user-a")
        db = object()
        with patch("app.api.routes.assets.create_asset_chat_session") as create_session:
            create_asset_chat_session_endpoint("asset-1", ChatSessionCreateRequest(title="A"), db, current_user)
        self.assertEqual(create_session.call_args.kwargs["user_id"], "user-a")

    def test_note_creation_uses_current_user_id(self) -> None:
        current_user = SimpleNamespace(id="user-b")
        db = object()
        payload = CreateNoteRequest(anchor=NoteAnchorPayload(anchor_type="text_selection", page_no=1, selected_text="abc"), content="note")
        with patch("app.api.routes.assets.create_asset_note") as create_note:
            create_asset_note_endpoint("asset-1", payload, db, current_user)
        self.assertEqual(create_note.call_args.kwargs["user_id"], "user-b")
```

- [ ] **Step 2: Run the failing propagation tests**

Run: `python -m unittest backend.tests.test_asset_user_isolation backend.tests.test_chat_user_isolation backend.tests.test_note_user_isolation -v`
Expected: FAIL because route functions still reference `settings.local_dev_user_id` or do not accept `current_user`.

- [ ] **Step 3: Add `current_user` to routes and pass `current_user.id` into services**

```python
# backend/app/api/routes/assets.py
from app.api.deps.auth import get_current_user
from app.models.user import User

@router.post("/{asset_id}/chat/sessions", response_model=ChatSessionItem)
def create_asset_chat_session_endpoint(
    asset_id: str,
    payload: ChatSessionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatSessionItem:
    return create_asset_chat_session(
        db=db,
        asset_id=asset_id,
        user_id=current_user.id,
        payload=payload,
    )

@router.post("/{asset_id}/notes", response_model=NoteItemResponse)
def create_asset_note_endpoint(
    asset_id: str,
    payload: CreateNoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteItemResponse:
    return create_asset_note(db=db, asset_id=asset_id, user_id=current_user.id, payload=payload)

@router.get("/{asset_id}/notes", response_model=NoteListResponse)
def list_asset_notes_endpoint(
    asset_id: str,
    anchor_type: AnchorType | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteListResponse:
    return list_asset_notes(db=db, asset_id=asset_id, user_id=current_user.id, anchor_type=anchor_type)

@router.post("/upload", response_model=AssetUploadResponse)
async def upload_asset_endpoint(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssetUploadResponse:
    content = await file.read()
    validate_pdf_upload(filename=file.filename, content_type=file.content_type or "application/pdf", content=content)
    return create_uploaded_asset(
        db=db,
        user_id=current_user.id,
        filename=file.filename or "paper.pdf",
        content_type=file.content_type or "application/pdf",
        content=content,
        title=title,
    )
```

```python
# backend/app/api/routes/chat.py
@router.get("/sessions/{session_id}/messages", response_model=ChatSessionMessagesResponse)
def list_chat_session_messages_endpoint(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatSessionMessagesResponse:
    return list_chat_session_messages(db, session_id, current_user.id)

@router.post("/sessions/{session_id}/messages", response_model=ChatMessageCreateResponse)
def create_chat_session_message_endpoint(
    session_id: str,
    payload: ChatMessageCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatMessageCreateResponse:
    return create_chat_session_message(db, session_id, current_user.id, payload)
```

```python
# backend/app/api/routes/notes.py
@router.patch("/{note_id}", response_model=NoteItemResponse)
def update_note_endpoint(
    note_id: str,
    payload: UpdateNoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteItemResponse:
    return update_note(db=db, note_id=note_id, user_id=current_user.id, payload=payload)
```

- [ ] **Step 4: Update service signatures so route inputs stay explicit**

```python
# backend/app/services/chat_service.py
def list_chat_session_messages(db: Session, session_id: str, user_id: str) -> ChatSessionMessagesResponse:
    ...


def create_chat_session_message(
    db: Session,
    session_id: str,
    user_id: str,
    payload: ChatMessageCreateRequest,
) -> ChatMessageCreateResponse:
    ...
```

```python
# backend/app/services/asset_create_service.py
def create_uploaded_asset(
    db: Session,
    user_id: str,
    filename: str,
    content_type: str,
    content: bytes,
    title: str | None = None,
) -> AssetUploadResponse:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前登录用户不存在。")
```

- [ ] **Step 5: Run the propagation tests again**

Run: `python -m unittest backend.tests.test_asset_user_isolation backend.tests.test_chat_user_isolation backend.tests.test_note_user_isolation -v`
Expected: PASS with route-to-service user propagation covered.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes/assets.py backend/app/api/routes/chat.py backend/app/api/routes/notes.py backend/app/services/chat_service.py backend/app/services/note_service.py backend/app/services/asset_create_service.py backend/tests/test_asset_user_isolation.py backend/tests/test_chat_user_isolation.py backend/tests/test_note_user_isolation.py
git commit -m "refactor: pass current user through api routes"
```

### Task 4: Add owner-check helpers for asset, reader, retrieval, and chat flows

**Files:**
- Modify: `backend/app/services/asset_service.py`
- Modify: `backend/app/services/asset_reader_service.py`
- Modify: `backend/app/services/retrieval_service.py`
- Modify: `backend/app/services/chat_service.py`
- Create: `backend/tests/test_reader_user_isolation.py`
- Modify: `backend/tests/test_asset_user_isolation.py`
- Modify: `backend/tests/test_chat_user_isolation.py`
- Test: `backend/tests/test_asset_user_isolation.py`
- Test: `backend/tests/test_reader_user_isolation.py`
- Test: `backend/tests/test_chat_user_isolation.py`

- [ ] **Step 1: Write failing tests for cross-user access returning 404**

```python
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import HTTPException

from app.services.asset_service import require_user_asset
from app.services.chat_service import require_user_session


class OwnerCheckTests(unittest.TestCase):
    def test_require_user_asset_rejects_other_users_asset(self) -> None:
        db = SimpleNamespace(get=lambda *_args, **_kwargs: None)
        with self.assertRaises(HTTPException) as ctx:
            require_user_asset(db, "asset-1", "user-a")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_require_user_session_rejects_other_users_session(self) -> None:
        db = SimpleNamespace(get=lambda *_args, **_kwargs: None)
        with self.assertRaises(HTTPException) as ctx:
            require_user_session(db, "session-1", "user-a")
        self.assertEqual(ctx.exception.status_code, 404)
```

- [ ] **Step 2: Run the failing owner-check tests**

Run: `python -m unittest backend.tests.test_asset_user_isolation backend.tests.test_reader_user_isolation backend.tests.test_chat_user_isolation -v`
Expected: FAIL because services still use `db.get(...)` or ignore `user_id`.

- [ ] **Step 3: Add user-scoped asset and session helpers and thread them into service reads**

```python
# backend/app/services/asset_service.py
from sqlalchemy import select


def require_user_asset(db: Session, asset_id: str, user_id: str) -> Asset:
    asset = db.scalars(select(Asset).where(Asset.id == asset_id, Asset.user_id == user_id)).first()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到对应的学习资产。")
    return asset


def list_assets(db: Session, user_id: str) -> list[AssetListItem]:
    assets = db.scalars(select(Asset).where(Asset.user_id == user_id).order_by(Asset.created_at.desc())).all()
    return [AssetListItem.model_validate(asset) for asset in assets]


def get_asset_detail(db: Session, asset_id: str, user_id: str) -> AssetDetail:
    asset = require_user_asset(db, asset_id, user_id)
    ...
    return _to_asset_detail(asset)
```

```python
# backend/app/services/asset_reader_service.py
from app.services.asset_service import require_user_asset


def get_asset_pdf_descriptor(db: Session, asset_id: str, user_id: str) -> AssetPdfDescriptor:
    require_user_asset(db, asset_id, user_id)
    asset_file = _get_latest_asset_file(db, asset_id, "original_pdf")
    ...


def get_asset_parsed_document(db: Session, asset_id: str, user_id: str) -> AssetParsedDocumentResponse:
    asset = require_user_asset(db, asset_id, user_id)
    ...
```

```python
# backend/app/services/chat_service.py
from app.services.asset_service import require_user_asset


def require_user_session(db: Session, session_id: str, user_id: str) -> ChatSession:
    statement = select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
    chat_session = db.scalars(statement).first()
    if chat_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到对应的问答会话。")
    return chat_session


def create_asset_chat_session(...):
    asset = require_user_asset(db, asset_id, user_id)


def list_asset_chat_sessions(db: Session, asset_id: str, user_id: str) -> list[ChatSessionItem]:
    require_user_asset(db, asset_id, user_id)
    ... where(ChatSession.asset_id == asset_id, ChatSession.user_id == user_id)


def create_chat_session_message(db: Session, session_id: str, user_id: str, payload: ChatMessageCreateRequest) -> ChatMessageCreateResponse:
    chat_session = require_user_session(db, session_id, user_id)
    asset = require_user_asset(db, chat_session.asset_id, user_id)
```

```python
# backend/app/services/retrieval_service.py
from app.services.asset_service import require_user_asset


def search_asset_chunks(
    db: Session,
    asset_id: str,
    query: str,
    top_k: int = 6,
    rewrite_query: bool = False,
    strategy: str = "s0",
    user_id: str | None = None,
) -> AssetRetrievalSearchResponse:
    if user_id is not None:
        require_user_asset(db, asset_id, user_id)
    else:
        _require_asset(db, asset_id)
    ...
```

- [ ] **Step 4: Update route calls so all read endpoints pass `current_user.id`**

```python
# backend/app/api/routes/assets.py
@router.get("", response_model=list[AssetListItem])
def list_asset_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AssetListItem]:
    return list_assets(db, current_user.id)

@router.get("/{asset_id}", response_model=AssetDetail)
def get_asset_detail_endpoint(
    asset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssetDetail:
    return get_asset_detail(db, asset_id, current_user.id)
```

- [ ] **Step 5: Run the isolation tests again**

Run: `python -m unittest backend.tests.test_asset_user_isolation backend.tests.test_reader_user_isolation backend.tests.test_chat_user_isolation -v`
Expected: PASS with cross-user reads rejected as `404`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/asset_service.py backend/app/services/asset_reader_service.py backend/app/services/retrieval_service.py backend/app/services/chat_service.py backend/app/api/routes/assets.py backend/tests/test_asset_user_isolation.py backend/tests/test_reader_user_isolation.py backend/tests/test_chat_user_isolation.py
git commit -m "fix: scope asset and chat reads by user"
```

### Task 5: Close owner-check gaps for notes, parse, mindmap, slides, and dev seed behavior

**Files:**
- Modify: `backend/app/services/note_service.py`
- Modify: `backend/app/services/document_parse_service.py`
- Modify: `backend/app/services/mindmap_service.py`
- Modify: `backend/app/services/slide_dsl_service.py`
- Modify: `backend/app/services/slide_generation_v2_service.py`
- Modify: `backend/app/services/slide_tts_service.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/asset_service.py`
- Modify: `.env.example`
- Modify: `README.md`
- Create: `backend/tests/test_slides_user_isolation.py`
- Modify: `backend/tests/test_note_user_isolation.py`
- Test: `backend/tests/test_note_user_isolation.py`
- Test: `backend/tests/test_slides_user_isolation.py`

- [ ] **Step 1: Write failing tests for note/slides isolation and gated dev seed**

```python
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import HTTPException

from app.services.note_service import _require_user_note
from app.services.asset_service import seed_dev_user_and_assets


class NoteAndSeedTests(unittest.TestCase):
    def test_require_user_note_keeps_returning_404_for_other_user(self) -> None:
        db = SimpleNamespace(scalars=lambda _statement: SimpleNamespace(first=lambda: None))
        with self.assertRaises(HTTPException) as ctx:
            _require_user_note(db, "note-1", "user-a")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_seed_dev_user_and_assets_is_noop_when_disabled(self) -> None:
        db = SimpleNamespace(committed=False, commit=lambda: None)
        result = seed_dev_user_and_assets(db, enabled=False)
        self.assertFalse(result)
```

- [ ] **Step 2: Run the failing tests**

Run: `python -m unittest backend.tests.test_note_user_isolation backend.tests.test_slides_user_isolation -v`
Expected: FAIL because seed gating and slides owner-check paths are incomplete.

- [ ] **Step 3: Apply user-scoped reads consistently across note/parse/mindmap/slides services**

```python
# backend/app/services/document_parse_service.py
from app.services.asset_service import require_user_asset


def get_asset_parse_status(db: Session, asset_id: str, user_id: str) -> AssetParseStatusResponse | None:
    asset = require_user_asset(db, asset_id, user_id)
    ...


def enqueue_asset_parse_retry(db: Session, asset_id: str, user_id: str) -> tuple[Asset, bool, str]:
    asset = require_user_asset(db, asset_id, user_id)
    ...
```

```python
# backend/app/services/mindmap_service.py
from app.services.asset_service import require_user_asset


def get_asset_mindmap(db: Session, asset_id: str, user_id: str) -> AssetMindmapResponse:
    asset = require_user_asset(db, asset_id, user_id)
    ...
```

```python
# backend/app/services/slide_dsl_service.py
from app.services.asset_service import require_user_asset


def get_asset_slides_snapshot(db: Session, asset_id: str, user_id: str) -> AssetSlidesResponse:
    asset = require_user_asset(db, asset_id, user_id)
    ...
```

```python
# backend/app/services/slide_tts_service.py
from app.services.asset_service import require_user_asset


def ensure_asset_slide_tts(db: Session, asset_id: str, user_id: str, page_index: int, prefetch_next: bool) -> AssetSlideTtsEnsureResponse:
    asset = require_user_asset(db, asset_id, user_id)
    ...
```

- [ ] **Step 4: Gate startup seed logic behind explicit config and remove implicit identity fallback**

```python
# backend/app/services/asset_service.py
def seed_dev_user_and_assets(db: Session, enabled: bool) -> bool:
    if not enabled:
        return False
    ...
    return True
```

```python
# backend/app/main.py
@asynccontextmanager
async def lifespan(_: FastAPI):
    db = SessionLocal()
    try:
        seed_dev_user_and_assets(db, enabled=settings.auth_dev_bypass_enabled)
        yield
    finally:
        db.close()
```

```dotenv
# .env.example
AUTH_JWT_SECRET=change-me-in-local-env
AUTH_ACCESS_TOKEN_EXPIRE_MINUTES=10080
AUTH_DEV_BYPASS_ENABLED=false
```

- [ ] **Step 5: Run the targeted tests again**

Run: `python -m unittest backend.tests.test_note_user_isolation backend.tests.test_slides_user_isolation backend.tests.test_slide_async_rebuild -v`
Expected: PASS with note/slides isolation and seed gating verified.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/note_service.py backend/app/services/document_parse_service.py backend/app/services/mindmap_service.py backend/app/services/slide_dsl_service.py backend/app/services/slide_generation_v2_service.py backend/app/services/slide_tts_service.py backend/app/main.py backend/app/services/asset_service.py .env.example README.md backend/tests/test_note_user_isolation.py backend/tests/test_slides_user_isolation.py
git commit -m "fix: close remaining user isolation gaps"
```

### Task 6: Build frontend auth store, bearer injection, guarded routes, and auth pages

**Files:**
- Create: `frontend/src/api/auth.ts`
- Create: `frontend/src/stores/auth.ts`
- Modify: `frontend/src/api/assets.ts`
- Modify: `frontend/src/router/routes.ts`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/main.ts`
- Modify: `frontend/src/App.vue`
- Create: `frontend/src/pages/auth/LoginPage.vue`
- Create: `frontend/src/pages/auth/RegisterPage.vue`
- Modify: `frontend/src/pages/workspace/WorkspacePage.vue`
- Modify: `frontend/src/components/PdfReaderPanel.vue`
- Test: `frontend/tests/e2e/spec18-auth.spec.ts`

- [ ] **Step 1: Write the failing Playwright auth-flow test**

```typescript
import { expect, test } from '@playwright/test';

test('redirects unauthenticated user to login and returns after login', async ({ page }) => {
  await page.route('**/api/auth/me', async (route) => {
    await route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: '登录态无效或已过期。' }) });
  });

  await page.goto('/library');
  await expect(page).toHaveURL(/\/login\?redirect=%2Flibrary/);
});
```

- [ ] **Step 2: Run the failing frontend auth test**

Run: `npm run test:e2e:spec18 --prefix frontend`
Expected: FAIL because the `spec18` script and auth pages/guards do not exist yet.

- [ ] **Step 3: Add auth API client, auth store, and centralized bearer header injection**

```typescript
// frontend/src/api/auth.ts
import { API_BASE_URL, parseErrorMessage, requestWithTimeout } from './assets';

export interface AuthUser {
  id: string;
  email: string;
  display_name: string;
  status: string;
  created_at: string;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: 'bearer';
  user: AuthUser;
}

export async function login(payload: { email: string; password: string }): Promise<AuthTokenResponse> {
  const response = await requestWithTimeout(`${API_BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await parseErrorMessage(response, `登录失败：${response.status}`));
  }
  return response.json() as Promise<AuthTokenResponse>;
}
```

```typescript
// frontend/src/stores/auth.ts
import { defineStore } from 'pinia';
import { fetchMe, login, register } from '@/api/auth';

const TOKEN_STORAGE_KEY = 'paper-learning.access-token';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem(TOKEN_STORAGE_KEY) ?? '',
    currentUser: null as null | Awaited<ReturnType<typeof fetchMe>>,
    bootstrapped: false,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token && state.currentUser),
  },
  actions: {
    getAuthHeader(): Record<string, string> {
      return this.token ? { Authorization: `Bearer ${this.token}` } : {};
    },
    async bootstrap() {
      if (!this.token) {
        this.bootstrapped = true;
        return;
      }
      try {
        this.currentUser = await fetchMe(this.token);
      } catch {
        this.logout();
      } finally {
        this.bootstrapped = true;
      }
    },
    async login(payload: { email: string; password: string }) {
      const response = await login(payload);
      this.token = response.access_token;
      localStorage.setItem(TOKEN_STORAGE_KEY, response.access_token);
      this.currentUser = response.user;
    },
    async register(payload: { email: string; password: string; display_name: string }) {
      const response = await register(payload);
      this.token = response.access_token;
      localStorage.setItem(TOKEN_STORAGE_KEY, response.access_token);
      this.currentUser = response.user;
    },
    logout() {
      this.token = '';
      this.currentUser = null;
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    },
  },
});
```

```typescript
// frontend/src/api/assets.ts
function withAuthHeaders(headers?: HeadersInit): HeadersInit {
  const token = localStorage.getItem('paper-learning.access-token');
  return token ? { ...(headers ?? {}), Authorization: `Bearer ${token}` } : (headers ?? {});
}

async function requestJson<T>(path: string): Promise<T> {
  const response = await requestWithTimeout(`${API_BASE_URL}${path}`, {
    headers: withAuthHeaders(),
  });
  ...
}
```

- [ ] **Step 4: Add route guards, auth pages, account shell, and update PDF loading path**

```typescript
// frontend/src/router/routes.ts
export const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/library' },
  { path: '/login', name: 'login', component: LoginPage },
  { path: '/register', name: 'register', component: RegisterPage },
  { path: '/library', name: 'library', component: LibraryPage, meta: { requiresAuth: true } },
  { path: '/workspace/:assetId', name: 'workspace', component: WorkspacePage, props: true, meta: { requiresAuth: true } },
  { path: '/workspace/:assetId/slides', name: 'slides-play', component: SlidesPlayPage, props: true, meta: { requiresAuth: true } },
]
```

```typescript
// frontend/src/router/index.ts
router.beforeEach(async (to) => {
  const authStore = useAuthStore();
  if (!authStore.bootstrapped) {
    await authStore.bootstrap();
  }
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } };
  }
  if ((to.name === 'login' || to.name === 'register') && authStore.isAuthenticated) {
    return { name: 'library' };
  }
  return true;
});
```

```vue
<!-- frontend/src/App.vue -->
<template>
  <div class="app-shell">
    <header v-if="showAccountBar" class="app-shell__header">
      <div>
        <strong>{{ authStore.currentUser?.display_name }}</strong>
        <span>{{ authStore.currentUser?.email }}</span>
      </div>
      <button type="button" class="toolbar-button toolbar-button--ghost" @click="handleLogout">退出登录</button>
    </header>
    <router-view />
  </div>
</template>
```

```typescript
// frontend/src/pages/workspace/WorkspacePage.vue
const pdfUrl = computed(() => pdfMeta.value ? `/api/assets/${assetId.value}/pdf` : '');
```

```vue
<!-- frontend/src/components/PdfReaderPanel.vue -->
const task = getDocument({
  url: props.pdfUrl,
  httpHeaders: localStorage.getItem('paper-learning.access-token')
    ? { Authorization: `Bearer ${localStorage.getItem('paper-learning.access-token')}` }
    : undefined,
  withCredentials: false,
});
```

- [ ] **Step 5: Build the frontend and run the auth E2E**

Run: `npm run build --prefix frontend && npm run test:e2e:spec18 --prefix frontend`
Expected: PASS with login redirect, bootstrap restore, and logout flow covered.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/auth.ts frontend/src/stores/auth.ts frontend/src/api/assets.ts frontend/src/router/index.ts frontend/src/router/routes.ts frontend/src/main.ts frontend/src/App.vue frontend/src/pages/auth/LoginPage.vue frontend/src/pages/auth/RegisterPage.vue frontend/src/pages/workspace/WorkspacePage.vue frontend/src/components/PdfReaderPanel.vue frontend/tests/e2e/spec18-auth.spec.ts frontend/package.json
git commit -m "feat: add frontend auth loop and guarded routes"
```

### Task 7: Add backend verification for register/login/me and user isolation

**Files:**
- Create: `backend/tests/test_auth_service.py`
- Create: `backend/tests/test_auth_dependency.py`
- Create: `backend/tests/test_auth_routes.py`
- Modify: `backend/tests/test_asset_user_isolation.py`
- Modify: `backend/tests/test_chat_user_isolation.py`
- Modify: `backend/tests/test_note_user_isolation.py`
- Modify: `backend/tests/test_reader_user_isolation.py`
- Modify: `backend/tests/test_slides_user_isolation.py`
- Test: `backend/tests/test_auth_service.py`
- Test: `backend/tests/test_auth_dependency.py`
- Test: `backend/tests/test_auth_routes.py`
- Test: `backend/tests/test_asset_user_isolation.py`
- Test: `backend/tests/test_chat_user_isolation.py`
- Test: `backend/tests/test_note_user_isolation.py`
- Test: `backend/tests/test_reader_user_isolation.py`
- Test: `backend/tests/test_slides_user_isolation.py`

- [ ] **Step 1: Expand tests to cover happy path and failure path auth semantics**

```python
class AuthServiceBehaviorTests(unittest.TestCase):
    def test_register_rejects_duplicate_email(self) -> None:
        ...

    def test_login_rejects_wrong_password(self) -> None:
        ...

    def test_decode_access_token_rejects_expired_token(self) -> None:
        ...
```

```python
class AuthDependencyBehaviorTests(unittest.TestCase):
    def test_get_current_user_rejects_unknown_subject(self) -> None:
        ...

    def test_get_current_user_returns_db_user(self) -> None:
        ...
```

- [ ] **Step 2: Run the focused backend verification suite and observe failures**

Run: `python -m unittest backend.tests.test_auth_service backend.tests.test_auth_dependency backend.tests.test_auth_routes backend.tests.test_asset_user_isolation backend.tests.test_chat_user_isolation backend.tests.test_note_user_isolation backend.tests.test_reader_user_isolation backend.tests.test_slides_user_isolation -v`
Expected: FAIL until all auth and owner-check branches are implemented.

- [ ] **Step 3: Fill in missing assertions for concrete behaviors rather than generic success paths**

```python
self.assertEqual(ctx.exception.status_code, 401)
self.assertEqual(str(ctx.exception.detail), "邮箱或密码错误。")
self.assertEqual(response.user.email, "alice@example.com")
self.assertEqual(asset_list_response[0].user_id, "user-a")
self.assertEqual(slides_response.asset_id, "asset-a")
```

- [ ] **Step 4: Re-run the focused backend verification suite**

Run: `python -m unittest backend.tests.test_auth_service backend.tests.test_auth_dependency backend.tests.test_auth_routes backend.tests.test_asset_user_isolation backend.tests.test_chat_user_isolation backend.tests.test_note_user_isolation backend.tests.test_reader_user_isolation backend.tests.test_slides_user_isolation -v`
Expected: PASS with auth and isolation regressions covered.

- [ ] **Step 5: Run an additional route/regression subset that touches slides and config**

Run: `python -m unittest backend.tests.test_runtime_config backend.tests.test_slide_async_rebuild backend.tests.test_slide_runtime_snapshot_service -v`
Expected: PASS, confirming Spec 18 changes did not break existing slides route behavior.

- [ ] **Step 6: Commit**

```bash
git add backend/tests/test_auth_service.py backend/tests/test_auth_dependency.py backend/tests/test_auth_routes.py backend/tests/test_asset_user_isolation.py backend/tests/test_chat_user_isolation.py backend/tests/test_note_user_isolation.py backend/tests/test_reader_user_isolation.py backend/tests/test_slides_user_isolation.py
git commit -m "test: cover auth and user isolation behavior"
```

### Task 8: Add browser acceptance coverage and update docs/handoff

**Files:**
- Create: `frontend/tests/e2e/spec18-auth.spec.ts`
- Modify: `frontend/tests/e2e/spec12-playback.spec.ts`
- Modify: `frontend/tests/e2e/spec12-docker-real.spec.ts`
- Modify: `docs/checklist.md`
- Modify: `docs/specs/spec-18-basic-user-system.md`
- Modify: `README.md`
- Modify: `.env.example`
- Test: `frontend/tests/e2e/spec18-auth.spec.ts`
- Test: `frontend/tests/e2e/spec12-playback.spec.ts`
- Test: `frontend/tests/e2e/spec12-docker-real.spec.ts`

- [ ] **Step 1: Extend E2E coverage to include auth bootstrap, redirect, and logout behavior**

```typescript
test('clears local auth state on logout and blocks protected route again', async ({ page }) => {
  await page.goto('/login');
  await page.fill('input[name="email"]', 'demo@example.com');
  await page.fill('input[name="password"]', 'paper-pass-123');
  await page.click('button[type="submit"]');
  await expect(page).toHaveURL(/\/library/);

  await page.getByRole('button', { name: '退出登录' }).click();
  await page.goto('/workspace/asset-e2e');
  await expect(page).toHaveURL(/\/login\?redirect=/);
});
```

- [ ] **Step 2: Update existing playback E2E so protected routes start from an authenticated state**

```typescript
await page.addInitScript(() => {
  localStorage.setItem('paper-learning.access-token', 'token-e2e');
});

await page.route('**/api/auth/me', async (route) => {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      id: 'user-e2e',
      email: 'demo@example.com',
      display_name: 'Spec18 E2E',
      status: 'active',
      created_at: new Date().toISOString(),
    }),
  });
});
```

- [ ] **Step 3: Run build and browser acceptance commands**

Run: `npm run build --prefix frontend && npm run test:e2e:spec18 --prefix frontend && npm run test:e2e:spec12 --prefix frontend`
Expected: PASS with auth and playback paths both green.

- [ ] **Step 4: Run one real docker-backed acceptance chain after backend auth is available**

Run: `npm run test:e2e:spec12:docker --prefix frontend`
Expected: PASS after the docker environment is updated to perform login or inject a valid bearer token before protected navigation.

- [ ] **Step 5: Update status docs and spec handoff with factual completion notes**

```markdown
# docs/checklist.md
- [x] Spec 18 后端认证主链路已落地：注册、登录、me、统一 current_user
- [x] 资产 / 阅读器 / 检索 / 问答 / 笔记 / Slides 读取已按 user_id 隔离
- [x] 前端已接入登录页、token 持久化、bootstrap、路由守卫与退出登录
- [ ] 历史 local-dev-user 资产仍保留，未自动迁移
```

```markdown
# docs/specs/spec-18-basic-user-system.md
### 本轮实现交接记录

- 已新增邮箱密码注册/登录与 Bearer Token 鉴权主链路
- 后端主路径不再使用 `settings.local_dev_user_id` 作为正式请求身份源
- 非本人资产、会话、笔记、Slides 访问统一返回 404
- 前端已实现登录页、注册页、受保护路由与退出登录
- 历史 `local-dev-user` 数据保留，但不自动迁移到真实注册用户
```

- [ ] **Step 6: Commit**

```bash
git add frontend/tests/e2e/spec18-auth.spec.ts frontend/tests/e2e/spec12-playback.spec.ts frontend/tests/e2e/spec12-docker-real.spec.ts docs/checklist.md docs/specs/spec-18-basic-user-system.md README.md .env.example
git commit -m "docs: record spec18 auth rollout and verification"
```

---

## Self-Review Checklist

- Spec coverage: this plan covers register/login/me/logout semantics, current-user dependency wiring, route replacement of `local_dev_user_id`, owner-check closure for assets/chat/notes/reader/slides, frontend auth loop, browser acceptance, and required docs updates.
- Placeholder scan: no `TODO`, `TBD`, or “similar to previous task” shortcuts remain.
- Type consistency: the plan consistently uses `current_user.id`, `AuthTokenResponse`, `CurrentUserResponse`, `require_user_asset`, and `require_user_session` naming across tasks.
- Scope check: this plan remains inside Spec 18 scope and avoids OAuth, password reset, RBAC, multi-tenant orgs, and historical asset migration.
