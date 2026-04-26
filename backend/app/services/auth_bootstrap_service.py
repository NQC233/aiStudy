from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.anchor import Anchor
from app.models.asset import Asset
from app.models.chat_session import ChatSession
from app.models.note import Note
from app.models.user import User


@dataclass(slots=True)
class DefaultAccountBootstrapResult:
    default_user: User | None
    created_default_user: bool
    migrated_asset_count: int
    migrated_chat_session_count: int
    migrated_anchor_count: int
    migrated_note_count: int


def _load_records_for_legacy_user(db: Session, model: type[Asset] | type[ChatSession] | type[Anchor] | type[Note]):
    return db.scalars(select(model).where(model.user_id == settings.local_dev_user_id)).all()


def ensure_default_account_and_migrate_legacy_data(
    db: Session,
    *,
    enabled: bool,
) -> DefaultAccountBootstrapResult:
    if not enabled:
        return DefaultAccountBootstrapResult(
            default_user=None,
            created_default_user=False,
            migrated_asset_count=0,
            migrated_chat_session_count=0,
            migrated_anchor_count=0,
            migrated_note_count=0,
        )

    default_user = db.get(User, settings.auth_default_account_id)
    if default_user is None:
        default_user = db.scalars(select(User).where(User.email == settings.auth_default_account_email)).first()

    created_default_user = default_user is None
    default_user_updated = False
    if default_user is None:
        default_user = User(
            id=settings.auth_default_account_id,
            email=settings.auth_default_account_email,
            display_name=settings.auth_default_account_name,
            password_hash=get_password_hash(settings.auth_default_account_password),
            status='active',
        )
        db.add(default_user)
        db.flush()
    else:
        target_password_hash = get_password_hash(settings.auth_default_account_password)
        if default_user.email != settings.auth_default_account_email:
            default_user.email = settings.auth_default_account_email
            default_user_updated = True
        if default_user.display_name != settings.auth_default_account_name:
            default_user.display_name = settings.auth_default_account_name
            default_user_updated = True
        if default_user.password_hash != target_password_hash:
            default_user.password_hash = target_password_hash
            default_user_updated = True
        if default_user.status != 'active':
            default_user.status = 'active'
            default_user_updated = True

    migrated_assets = _load_records_for_legacy_user(db, Asset)
    migrated_chat_sessions = _load_records_for_legacy_user(db, ChatSession)
    migrated_anchors = _load_records_for_legacy_user(db, Anchor)
    migrated_notes = _load_records_for_legacy_user(db, Note)

    for record in [*migrated_assets, *migrated_chat_sessions, *migrated_anchors, *migrated_notes]:
        record.user_id = default_user.id

    if created_default_user or default_user_updated or migrated_assets or migrated_chat_sessions or migrated_anchors or migrated_notes:
        db.commit()

    return DefaultAccountBootstrapResult(
        default_user=default_user,
        created_default_user=created_default_user,
        migrated_asset_count=len(migrated_assets),
        migrated_chat_session_count=len(migrated_chat_sessions),
        migrated_anchor_count=len(migrated_anchors),
        migrated_note_count=len(migrated_notes),
    )
