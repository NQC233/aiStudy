from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def generate_document_parse_id() -> str:
    """生成解析记录主键。"""
    return str(uuid4())


class DocumentParse(Base):
    """文档解析记录。

    首期只围绕 MinerU 解析链路建立最小记录，后续知识库和阅读器都将基于该记录消费解析产物。
    """

    __tablename__ = "document_parses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_document_parse_id)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="mineru")
    parse_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    markdown_storage_key: Mapped[str | None] = mapped_column(String(512))
    json_storage_key: Mapped[str | None] = mapped_column(String(512))
    raw_response_storage_key: Mapped[str | None] = mapped_column(String(512))
    parser_meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    asset = relationship("Asset", back_populates="document_parses")
