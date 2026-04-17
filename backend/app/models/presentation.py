from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def generate_presentation_id() -> str:
    return str(uuid4())


class Presentation(Base):
    __tablename__ = "presentations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_presentation_id
    )
    asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id"), nullable=False, unique=True, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    lesson_plan: Mapped[dict | None] = mapped_column(JSONB)
    slides_dsl: Mapped[dict | None] = mapped_column(JSONB)
    analysis_pack: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    visual_asset_catalog: Mapped[list[dict]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    presentation_plan: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    scene_specs: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    rendered_slide_pages: Mapped[list[dict]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    runtime_bundle: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    tts_manifest: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    playback_plan: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    dsl_quality_report: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    dsl_fix_logs: Mapped[list[dict]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    error_meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    active_run_token: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    asset = relationship("Asset", back_populates="presentation")
