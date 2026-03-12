from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def generate_mindmap_node_id() -> str:
    """生成导图节点主键。"""
    return str(uuid4())


class MindmapNode(Base):
    """导图节点与原文映射。"""

    __tablename__ = "mindmap_nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_mindmap_node_id)
    mindmap_id: Mapped[str] = mapped_column(ForeignKey("mindmaps.id"), nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("mindmap_nodes.id"), index=True)
    node_key: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_no: Mapped[int | None] = mapped_column(Integer)
    paragraph_ref: Mapped[str | None] = mapped_column(String(64))
    section_path: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    block_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    selector_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    mindmap = relationship("Mindmap", back_populates="nodes")
    parent = relationship("MindmapNode", remote_side=[id], back_populates="children")
    children = relationship("MindmapNode", back_populates="parent")
