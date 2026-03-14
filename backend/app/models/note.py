from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def generate_note_id() -> str:
    """生成笔记主键。"""
    return str(uuid4())


class Note(Base):
    """资产内的锚点笔记。"""

    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_note_id)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    anchor_id: Mapped[str] = mapped_column(ForeignKey("anchors.id"), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )

    asset = relationship("Asset", back_populates="notes")
    user = relationship("User", back_populates="notes")
    anchor = relationship("Anchor", back_populates="notes")
