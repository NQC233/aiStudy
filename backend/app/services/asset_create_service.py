from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.asset import Asset
from app.models.asset_file import AssetFile
from app.models.user import User
from app.schemas.asset import AssetDetail
from app.schemas.asset_upload import AssetUploadResponse
from app.services.asset_service import _to_asset_detail
from app.services.oss_service import OSSConfigurationError, upload_pdf_bytes


def validate_pdf_upload(filename: str | None, content_type: str | None, content: bytes) -> None:
    """对上传文件做基础校验。"""
    if not filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传文件缺少文件名。")

    suffix = Path(filename).suffix.lower()
    if suffix != ".pdf":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前仅支持上传 PDF 文件。")

    if content_type and content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传文件的 MIME 类型不是 PDF。")

    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传文件为空。")

    max_size = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"上传文件超过 {settings.max_upload_size_mb}MB 限制。",
        )


def create_uploaded_asset(
    db: Session,
    user_id: str,
    filename: str,
    content_type: str,
    content: bytes,
    title: str | None = None,
) -> AssetUploadResponse:
    """创建上传资产，并将原始 PDF 保存到 OSS。"""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="本地开发用户不存在。")

    asset = Asset(
        user_id=user_id,
        source_type="upload",
        title=(title or Path(filename).stem).strip() or "未命名论文",
        authors=[],
        abstract=None,
        language="unknown",
        status="draft",
        parse_status="not_started",
        parse_error_message=None,
        kb_status="not_started",
        mindmap_status="not_started",
    )
    db.add(asset)
    db.flush()

    try:
        upload_result = upload_pdf_bytes(
            user_id=user_id,
            asset_id=asset.id,
            filename=filename,
            content=content,
            content_type=content_type,
        )
    except OSSConfigurationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - 这里统一兜底第三方异常
        db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="上传 PDF 到 OSS 失败。") from exc

    asset_file = AssetFile(
        asset_id=asset.id,
        file_type="original_pdf",
        storage_key=upload_result.storage_key,
        public_url=upload_result.public_url,
        mime_type=content_type,
        size=len(content),
    )
    db.add(asset_file)

    # 上传成功后立即交给 Celery Worker 执行真实解析链路。
    asset.status = "queued"
    asset.parse_status = "queued"
    asset.parse_error_message = None

    db.commit()
    db.refresh(asset)
    db.refresh(asset_file)

    # 延迟导入任务，避免 worker 初始化时 services 与 tasks 互相导入。
    from app.workers.tasks import enqueue_parse_asset

    enqueue_parse_asset.delay(asset.id)

    return AssetUploadResponse(
        asset=_to_asset_detail(asset),
        uploaded_file_id=asset_file.id,
        uploaded_file_url=asset_file.public_url,
    )
