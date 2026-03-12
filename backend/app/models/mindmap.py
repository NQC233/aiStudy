from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def generate_mindmap_id() -> str:
    """生成导图主键。"""
    return str(uuid4())


class Mindmap(Base):
    """资产导图快照。"""

    __tablename__ = "mindmaps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_mindmap_id)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    storage_key: Mapped[str | None] = mapped_column(String(512))
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    asset = relationship("Asset", back_populates="mindmaps")
    nodes = relationship("MindmapNode", back_populates="mindmap", cascade="all, delete-orphan")
