from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas.anchor import AssetAnchorPreviewRequest, AssetAnchorPreviewResponse
from app.schemas.asset import AssetDetail, AssetListItem
from app.schemas.document_parse import AssetParseRetryResponse, AssetParseStatusResponse
from app.schemas.reader import AssetParsedDocumentResponse, AssetPdfDescriptor
from app.schemas.asset_upload import AssetUploadResponse
from app.services import create_uploaded_asset, enqueue_asset_parse_retry, get_asset_parse_status, validate_pdf_upload
from app.services.asset_reader_service import (
    get_asset_parsed_document,
    get_asset_pdf_content,
    get_asset_pdf_descriptor,
    preview_asset_anchor,
)
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


@router.get("/{asset_id}/pdf-meta", response_model=AssetPdfDescriptor, summary="获取阅读器 PDF 地址")
def get_asset_pdf_meta_endpoint(asset_id: str, db: Session = Depends(get_db)) -> AssetPdfDescriptor:
    """返回阅读器加载 PDF 所需的元信息。"""
    return get_asset_pdf_descriptor(db, asset_id)


@router.get("/{asset_id}/pdf", summary="获取原始 PDF 内容")
def get_asset_pdf_endpoint(asset_id: str, db: Session = Depends(get_db)) -> Response:
    """代理原始 PDF，避免前端直接依赖 OSS 跨域配置。"""
    content, content_type = get_asset_pdf_content(db, asset_id)
    return Response(content=content, media_type=content_type)


@router.get("/{asset_id}/parsed-json", response_model=AssetParsedDocumentResponse, summary="获取 parsed_json")
def get_asset_parsed_json_endpoint(asset_id: str, db: Session = Depends(get_db)) -> AssetParsedDocumentResponse:
    """返回阅读器目录、块级定位和锚点索引所需的 parsed_json。"""
    return get_asset_parsed_document(db, asset_id)


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


@router.post(
    "/{asset_id}/anchor-preview",
    response_model=AssetAnchorPreviewResponse,
    summary="校验并返回标准化锚点对象",
)
def preview_asset_anchor_endpoint(
    asset_id: str,
    payload: AssetAnchorPreviewRequest,
    db: Session = Depends(get_db),
) -> AssetAnchorPreviewResponse:
    """首期只做结构校验和标准化，不做持久化。"""
    return preview_asset_anchor(db, asset_id, payload)


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
