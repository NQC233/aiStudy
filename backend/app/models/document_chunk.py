from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def generate_document_chunk_id() -> str:
    """生成 chunk 主键。"""
    return str(uuid4())


class DocumentChunk(Base):
    """资产级知识库 chunk。

    每条记录都需要保留 block/page/paragraph/section 信息，供后续引用回跳直接复用。
    """

    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_document_chunk_id)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), nullable=False, index=True)
    parse_id: Mapped[str] = mapped_column(ForeignKey("document_parses.id"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section_path: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    paragraph_start: Mapped[int | None] = mapped_column(Integer)
    paragraph_end: Mapped[int | None] = mapped_column(Integer)
    block_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_started")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    asset = relationship("Asset", back_populates="document_chunks")
    parse = relationship("DocumentParse", back_populates="document_chunks")
