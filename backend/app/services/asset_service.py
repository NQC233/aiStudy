from __future__ import annotations

from urllib.parse import unquote, urlparse

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.asset import Asset
from app.models.asset_file import AssetFile
from app.models.user import User
from app.schemas.asset import (
    AssetDeleteResponse,
    AssetDetail,
    AssetListItem,
    BasicResourceStatus,
    EnhancedResourceStatus,
)
from app.services.oss_service import (
    OSSConfigurationError,
    delete_asset_prefix_objects,
    delete_objects,
)


def _to_asset_detail(asset: Asset) -> AssetDetail:
    """将 ORM 模型转换为详情响应结构。"""
    return AssetDetail(
        id=asset.id,
        user_id=asset.user_id,
        title=asset.title,
        authors=asset.authors,
        abstract=asset.abstract,
        source_type=asset.source_type,
        language=asset.language,
        status=asset.status,
        parse_error_message=asset.parse_error_message,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
        basic_resources=BasicResourceStatus(
            parse_status=asset.parse_status,
            kb_status=asset.kb_status,
            mindmap_status=asset.mindmap_status,
        ),
        enhanced_resources=EnhancedResourceStatus(
            slides_status=asset.slides_status,
            anki_status=asset.anki_status,
            quiz_status=asset.quiz_status,
        ),
    )


def list_assets(db: Session) -> list[AssetListItem]:
    """返回图书馆资产列表。"""
    statement = select(Asset).order_by(Asset.created_at.desc())
    assets = db.scalars(statement).all()
    return [AssetListItem.model_validate(asset) for asset in assets]


def get_asset_detail(db: Session, asset_id: str) -> AssetDetail | None:
    """返回单个资产详情。"""
    asset = db.get(Asset, asset_id)
    if asset is None:
        return None
    return _to_asset_detail(asset)


def extract_storage_key_from_public_url(public_url: str | None) -> str | None:
    if not public_url:
        return None
    parsed = urlparse(public_url)
    key = unquote(parsed.path or "").lstrip("/")
    return key or None


def collect_asset_storage_keys(asset: Asset) -> set[str]:
    keys: set[str] = set()

    for file in asset.files:
        if file.storage_key:
            keys.add(file.storage_key.strip().lstrip("/"))

    for parse in asset.document_parses:
        for candidate in (
            parse.markdown_storage_key,
            parse.json_storage_key,
            parse.raw_response_storage_key,
        ):
            if candidate:
                keys.add(candidate.strip().lstrip("/"))

    for mindmap in asset.mindmaps:
        if mindmap.storage_key:
            keys.add(mindmap.storage_key.strip().lstrip("/"))

    presentation = asset.presentation
    if presentation and isinstance(presentation.tts_manifest, dict):
        pages = presentation.tts_manifest.get("pages") or []
        if isinstance(pages, list):
            for page in pages:
                if not isinstance(page, dict):
                    continue
                audio_key = extract_storage_key_from_public_url(page.get("audio_url"))
                if audio_key:
                    keys.add(audio_key)

    keys.discard("")
    return keys


def delete_asset(db: Session, asset_id: str) -> AssetDeleteResponse:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到对应的学习资产。",
        )

    storage_keys = sorted(collect_asset_storage_keys(asset))
    deleted_oss_count = 0
    failed_oss_keys: list[str] = []
    warning: str | None = None

    try:
        deleted_count, failed_keys = delete_objects(storage_keys)
        deleted_oss_count += deleted_count
        failed_oss_keys.extend(failed_keys)

        prefix_deleted_count, prefix_failed_keys = delete_asset_prefix_objects(
            user_id=asset.user_id,
            asset_id=asset.id,
        )
        deleted_oss_count += prefix_deleted_count
        failed_oss_keys.extend(prefix_failed_keys)
    except OSSConfigurationError:
        warning = "OSS 未配置，已删除数据库记录，但未执行对象存储清理。"

    db.delete(asset)
    db.commit()

    if failed_oss_keys:
        warning = (
            "已删除数据库记录，但有部分 OSS 文件删除失败，"
            f"请检查对象存储权限或网络（失败 {len(set(failed_oss_keys))} 个）。"
        )

    return AssetDeleteResponse(
        asset_id=asset_id,
        deleted=True,
        deleted_oss_count=deleted_oss_count,
        failed_oss_count=len(set(failed_oss_keys)),
        warning=warning,
    )


def seed_dev_user_and_assets(db: Session) -> None:
    """在单用户开发模式下写入最小测试数据。"""
    user = db.get(User, settings.local_dev_user_id)
    if user is None:
        user = User(
            id=settings.local_dev_user_id,
            email=settings.local_dev_user_email,
            display_name=settings.local_dev_user_name,
            status="active",
        )
        db.add(user)
        db.flush()

    asset_count = db.scalar(select(func.count()).select_from(Asset))
    if asset_count:
        db.commit()
        return

    demo_assets = [
        Asset(
            user_id=user.id,
            source_type="preset",
            title="Attention Is All You Need",
            authors=[
                "Ashish Vaswani",
                "Noam Shazeer",
                "Niki Parmar",
                "Jakob Uszkoreit",
            ],
            abstract="提出 Transformer 架构，使用自注意力机制替代循环结构，显著改善机器翻译性能与并行效率。",
            language="en",
            status="ready",
            parse_status="ready",
            kb_status="ready",
            mindmap_status="processing",
        ),
        Asset(
            user_id=user.id,
            source_type="upload",
            title="Segment Anything",
            authors=["Alexander Kirillov", "Eric Mintun", "Nikhila Ravi"],
            abstract="构建通用图像分割基础模型，目标是在更大范围的视觉任务中提供高可迁移能力。",
            language="en",
            status="processing",
            parse_status="processing",
            kb_status="not_started",
            mindmap_status="not_started",
        ),
    ]

    db.add_all(demo_assets)
    db.flush()

    demo_files = [
        AssetFile(
            asset_id=demo_assets[0].id,
            file_type="original_pdf",
            storage_key="seed/preset/attention.pdf",
            public_url="https://nqc.asia/seed/preset/attention.pdf",
            mime_type="application/pdf",
            size=1024,
        ),
        AssetFile(
            asset_id=demo_assets[1].id,
            file_type="original_pdf",
            storage_key="seed/upload/segment-anything.pdf",
            public_url="https://nqc.asia/seed/upload/segment-anything.pdf",
            mime_type="application/pdf",
            size=1024,
        ),
    ]

    db.add_all(demo_files)
    db.commit()
