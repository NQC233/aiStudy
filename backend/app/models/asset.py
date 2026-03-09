from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def generate_asset_id() -> str:
    """生成资产主键，保持首期接口与未来 UUID 方案兼容。"""
    return str(uuid4())


class Asset(Base):
    """学习资产模型。

    这里先聚焦图书馆和详情页所需字段，同时为后续解析、知识库和导图状态预留占位。
    """

    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_asset_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    authors: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    abstract: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    parse_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_started")
    parse_error_message: Mapped[str | None] = mapped_column(Text)
    kb_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_started")
    mindmap_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_started")
    slides_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_generated")
    anki_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_generated")
    quiz_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_generated")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship("User", back_populates="assets")
    files = relationship("AssetFile", back_populates="asset", cascade="all, delete-orphan")
    document_parses = relationship("DocumentParse", back_populates="asset", cascade="all, delete-orphan")
    document_chunks = relationship("DocumentChunk", back_populates="asset", cascade="all, delete-orphan")
