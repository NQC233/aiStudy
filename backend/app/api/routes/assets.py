from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas.asset import AssetDetail, AssetListItem
from app.schemas.document_parse import AssetParseRetryResponse, AssetParseStatusResponse
from app.schemas.asset_upload import AssetUploadResponse
from app.services import create_uploaded_asset, enqueue_asset_parse_retry, get_asset_parse_status, validate_pdf_upload
from app.services.asset_service import get_asset_detail, list_assets
from app.workers.tasks import enqueue_parse_asset

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


@router.get("/{asset_id}/status", response_model=AssetParseStatusResponse, summary="获取资产解析状态")
def get_asset_status_endpoint(asset_id: str, db: Session = Depends(get_db)) -> AssetParseStatusResponse:
    """返回当前资产和最近一次解析任务的状态摘要。"""
    parse_status = get_asset_parse_status(db, asset_id)
    if parse_status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到对应的学习资产。",
        )
    return parse_status


@router.get("/{asset_id}/parse", response_model=AssetParseStatusResponse, summary="获取资产解析详情")
def get_asset_parse_endpoint(asset_id: str, db: Session = Depends(get_db)) -> AssetParseStatusResponse:
    """首期解析详情直接复用状态结构，后续可单独扩展。"""
    parse_status = get_asset_parse_status(db, asset_id)
    if parse_status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到对应的学习资产。",
        )
    return parse_status


@router.post("/{asset_id}/parse/retry", response_model=AssetParseRetryResponse, summary="重试资产解析")
def retry_asset_parse_endpoint(asset_id: str, db: Session = Depends(get_db)) -> AssetParseRetryResponse:
    """将失败或未开始的资产重新推进到解析队列。"""
    asset, should_enqueue = enqueue_asset_parse_retry(db, asset_id)
    if should_enqueue:
        enqueue_parse_asset.delay(asset.id)
    return AssetParseRetryResponse(
        asset_id=asset.id,
        parse_status=asset.parse_status,
        message="已重新加入解析队列。" if should_enqueue else "当前资产已在解析队列中。",
    )


@router.post("/upload", response_model=AssetUploadResponse, summary="上传 PDF 并创建学习资产")
async def upload_asset_endpoint(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> AssetUploadResponse:
    """上传单个 PDF 文件，完成 OSS 存储与资产创建。"""
    content = await file.read()
    content_type = file.content_type or "application/pdf"

    validate_pdf_upload(filename=file.filename, content_type=content_type, content=content)
    return create_uploaded_asset(
        db=db,
        user_id=settings.local_dev_user_id,
        filename=file.filename or "paper.pdf",
        content_type=content_type,
        content=content,
        title=title,
    )
