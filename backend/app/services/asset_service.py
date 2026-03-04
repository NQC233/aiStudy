from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.asset import Asset
from app.models.asset_file import AssetFile
from app.models.user import User
from app.schemas.asset import AssetDetail, AssetListItem, BasicResourceStatus, EnhancedResourceStatus


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
