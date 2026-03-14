from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def generate_anchor_id() -> str:
    """生成锚点主键。"""
    return str(uuid4())


class Anchor(Base):
    """统一锚点模型，承载文本选区和导图节点等定位语义。"""

    __tablename__ = "anchors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_anchor_id)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    anchor_type: Mapped[str] = mapped_column(String(32), nullable=False, default="text_selection")
    page_no: Mapped[int | None] = mapped_column(Integer, index=True)
    block_id: Mapped[str | None] = mapped_column(String(128), index=True)
    paragraph_no: Mapped[int | None] = mapped_column(Integer)
    selected_text: Mapped[str | None] = mapped_column(Text)
    selector_type: Mapped[str] = mapped_column(String(64), nullable=False, default="block")
    selector_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    asset = relationship("Asset", back_populates="anchors")
    user = relationship("User", back_populates="anchors")
    notes = relationship("Note", back_populates="anchor", cascade="all, delete-orphan")
