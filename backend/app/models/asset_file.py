from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def generate_asset_file_id() -> str:
    """生成资产文件主键。"""
    return str(uuid4())


class AssetFile(Base):
    """学习资产关联文件。

    首期只存原始 PDF，后续可逐步接入 parsed_json、markdown 和衍生图片。
    """

    __tablename__ = "asset_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_asset_file_id)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), nullable=False, index=True)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    public_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    asset = relationship("Asset", back_populates="files")
