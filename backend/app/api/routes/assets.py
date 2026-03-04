from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.asset import AssetDetail, AssetListItem
from app.services.asset_service import get_asset_detail, list_assets

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("", response_model=list[AssetListItem], summary="获取资产列表")
def list_asset_endpoint(db: Session = Depends(get_db)) -> list[AssetListItem]:
    """返回图书馆页所需的资产列表。"""
    return list_assets(db)


@router.get("/{asset_id}", response_model=AssetDetail, summary="获取资产详情")
def get_asset_detail_endpoint(asset_id: str, db: Session = Depends(get_db)) -> AssetDetail:
    """返回工作区占位页所需的资产详情。"""
    asset = get_asset_detail(db, asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到对应的学习资产。",
        )
    return asset
