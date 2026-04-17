from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas.anchor import AssetAnchorPreviewRequest, AssetAnchorPreviewResponse
from app.schemas.asset import AssetDeleteResponse, AssetDetail, AssetListItem
from app.schemas.document_chunk import (
    AssetChunkListResponse,
    AssetChunkRebuildResponse,
    AssetRetrievalSearchRequest,
    AssetRetrievalSearchResponse,
)
from app.schemas.document_parse import AssetParseRetryResponse, AssetParseStatusResponse
from app.schemas.mindmap import AssetMindmapRebuildResponse, AssetMindmapResponse
from app.schemas.note import (
    AnchorType,
    CreateNoteRequest,
    NoteItemResponse,
    NoteListResponse,
)
from app.schemas.reader import AssetParsedDocumentResponse, AssetPdfDescriptor
from app.schemas.slide_dsl import (
    AssetSlideTtsEnsureRequest,
    AssetSlideTtsEnsureResponse,
    AssetSlideTtsRetryNextRequest,
    AssetSlideTtsRetryNextResponse,
    AssetSlidesResponse,
)
from app.schemas.asset_upload import AssetUploadResponse
from app.schemas.chat import ChatSessionCreateRequest, ChatSessionItem
from app.services import (
    create_asset_note,
    create_asset_chat_session,
    create_uploaded_asset,
    enqueue_asset_mindmap_rebuild,
    enqueue_asset_chunk_rebuild,
    enqueue_asset_parse_retry,
    ensure_asset_slide_tts,
    generate_asset_slides_runtime_bundle,
    get_asset_mindmap,
    get_asset_slides_snapshot,
    get_asset_parse_status,
    list_asset_notes,
    list_asset_chat_sessions,
    list_asset_chunks,
    retry_next_asset_slide_tts,
    search_asset_chunks,
    validate_pdf_upload,
)
from app.services.asset_reader_service import (
    get_asset_parsed_document,
    get_asset_pdf_content,
    get_asset_pdf_descriptor,
    preview_asset_anchor,
)
from app.services.asset_service import delete_asset, get_asset_detail, list_assets
from app.workers.tasks import (
    enqueue_build_asset_kb,
    enqueue_generate_asset_mindmap,
    enqueue_generate_asset_slide_tts,
    enqueue_parse_asset,
)

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("", response_model=list[AssetListItem], summary="获取资产列表")
def list_asset_endpoint(db: Session = Depends(get_db)) -> list[AssetListItem]:
    """返回图书馆页所需的资产列表。"""
    return list_assets(db)


@router.get("/{asset_id}", response_model=AssetDetail, summary="获取资产详情")
def get_asset_detail_endpoint(
    asset_id: str, db: Session = Depends(get_db)
) -> AssetDetail:
    """返回工作区占位页所需的资产详情。"""
    asset = get_asset_detail(db, asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到对应的学习资产。",
        )
    return asset


@router.delete("/{asset_id}", response_model=AssetDeleteResponse, summary="删除学习资产")
def delete_asset_endpoint(
    asset_id: str,
    db: Session = Depends(get_db),
) -> AssetDeleteResponse:
    """删除资产及其关联数据，并尽量清理 OSS 存储对象。"""
    return delete_asset(db, asset_id)


@router.get(
    "/{asset_id}/pdf-meta",
    response_model=AssetPdfDescriptor,
    summary="获取阅读器 PDF 地址",
)
def get_asset_pdf_meta_endpoint(
    asset_id: str, db: Session = Depends(get_db)
) -> AssetPdfDescriptor:
    """返回阅读器加载 PDF 所需的元信息。"""
    return get_asset_pdf_descriptor(db, asset_id)


@router.get("/{asset_id}/pdf", summary="获取原始 PDF 内容")
def get_asset_pdf_endpoint(asset_id: str, db: Session = Depends(get_db)) -> Response:
    """代理原始 PDF，避免前端直接依赖 OSS 跨域配置。"""
    content, content_type = get_asset_pdf_content(db, asset_id)
    return Response(content=content, media_type=content_type)


@router.get(
    "/{asset_id}/parsed-json",
    response_model=AssetParsedDocumentResponse,
    summary="获取 parsed_json",
)
def get_asset_parsed_json_endpoint(
    asset_id: str, db: Session = Depends(get_db)
) -> AssetParsedDocumentResponse:
    """返回阅读器目录、块级定位和锚点索引所需的 parsed_json。"""
    return get_asset_parsed_document(db, asset_id)


@router.get(
    "/{asset_id}/mindmap", response_model=AssetMindmapResponse, summary="获取资产导图"
)
def get_asset_mindmap_endpoint(
    asset_id: str, db: Session = Depends(get_db)
) -> AssetMindmapResponse:
    """返回当前资产可用的导图节点与映射信息。"""
    return get_asset_mindmap(db, asset_id)


@router.get(
    "/{asset_id}/status",
    response_model=AssetParseStatusResponse,
    summary="获取资产解析状态",
)
def get_asset_status_endpoint(
    asset_id: str, db: Session = Depends(get_db)
) -> AssetParseStatusResponse:
    """返回当前资产和最近一次解析任务的状态摘要。"""
    parse_status = get_asset_parse_status(db, asset_id)
    if parse_status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到对应的学习资产。",
        )
    return parse_status


@router.get(
    "/{asset_id}/parse",
    response_model=AssetParseStatusResponse,
    summary="获取资产解析详情",
)
def get_asset_parse_endpoint(
    asset_id: str, db: Session = Depends(get_db)
) -> AssetParseStatusResponse:
    """首期解析详情直接复用状态结构，后续可单独扩展。"""
    parse_status = get_asset_parse_status(db, asset_id)
    if parse_status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到对应的学习资产。",
        )
    return parse_status


@router.get(
    "/{asset_id}/slides",
    response_model=AssetSlidesResponse,
    summary="获取资产 slides DSL 与质量报告",
)
def get_asset_slides_endpoint(
    asset_id: str,
    db: Session = Depends(get_db),
) -> AssetSlidesResponse:
    """返回当前可用的 slides 播放快照。"""
    return get_asset_slides_snapshot(db, asset_id)


@router.post(
    "/{asset_id}/slides/runtime-bundle/rebuild",
    response_model=AssetSlidesResponse,
    summary="重建资产 runtime bundle slides",
)
def rebuild_asset_runtime_bundle_slides_endpoint(
    asset_id: str,
    db: Session = Depends(get_db),
) -> AssetSlidesResponse:
    """同步执行新主链路，生成并持久化 runtime bundle。"""
    generate_asset_slides_runtime_bundle(db, asset_id=asset_id)
    return get_asset_slides_snapshot(db, asset_id)


@router.post(
    "/{asset_id}/slides/tts/ensure",
    response_model=AssetSlideTtsEnsureResponse,
    summary="触发当前页与下一页 TTS 生成",
)
def ensure_asset_slide_tts_endpoint(
    asset_id: str,
    payload: AssetSlideTtsEnsureRequest,
    db: Session = Depends(get_db),
) -> AssetSlideTtsEnsureResponse:
    """按播放进度触发当前页懒生成，并可预取下一页。"""
    response = ensure_asset_slide_tts(
        db,
        asset_id=asset_id,
        page_index=payload.page_index,
        prefetch_next=payload.prefetch_next,
    )
    for slide_key in response.enqueued_slide_keys:
        enqueue_generate_asset_slide_tts.delay(asset_id, slide_key)
    return response


@router.post(
    "/{asset_id}/slides/tts/retry-next",
    response_model=AssetSlideTtsRetryNextResponse,
    summary="重试下一页 TTS 生成",
)
def retry_next_asset_slide_tts_endpoint(
    asset_id: str,
    payload: AssetSlideTtsRetryNextRequest,
    db: Session = Depends(get_db),
) -> AssetSlideTtsRetryNextResponse:
    """自动播放暂停后，重试下一页失败任务并重新入队。"""
    response = retry_next_asset_slide_tts(
        db,
        asset_id=asset_id,
        current_page_index=payload.current_page_index,
    )
    for slide_key in response.enqueued_slide_keys:
        enqueue_generate_asset_slide_tts.delay(asset_id, slide_key)
    return response


@router.post(
    "/{asset_id}/parse/retry",
    response_model=AssetParseRetryResponse,
    summary="重试资产解析",
)
def retry_asset_parse_endpoint(
    asset_id: str, db: Session = Depends(get_db)
) -> AssetParseRetryResponse:
    """将失败或未开始的资产重新推进到解析队列。"""
    asset, should_enqueue, message = enqueue_asset_parse_retry(db, asset_id)
    if should_enqueue:
        enqueue_parse_asset.delay(asset.id)
    return AssetParseRetryResponse(
        asset_id=asset.id,
        parse_status=asset.parse_status,
        message=message,
    )


@router.get(
    "/{asset_id}/chunks",
    response_model=AssetChunkListResponse,
    summary="获取资产 chunk 列表",
)
def list_asset_chunks_endpoint(
    asset_id: str,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> AssetChunkListResponse:
    """用于调试 chunk 构建结果和引用映射。"""
    return list_asset_chunks(db, asset_id=asset_id, limit=limit)


@router.post(
    "/{asset_id}/chunks/rebuild",
    response_model=AssetChunkRebuildResponse,
    summary="重建资产知识库",
)
def rebuild_asset_chunks_endpoint(
    asset_id: str, db: Session = Depends(get_db)
) -> AssetChunkRebuildResponse:
    """将当前资产推进到知识库重建队列。"""
    asset, should_enqueue = enqueue_asset_chunk_rebuild(db, asset_id)
    if should_enqueue:
        enqueue_build_asset_kb.delay(asset.id)
    return AssetChunkRebuildResponse(
        asset_id=asset.id,
        kb_status=asset.kb_status,
        message="已加入知识库重建队列。"
        if should_enqueue
        else "当前资产知识库正在构建中。",
    )


@router.post(
    "/{asset_id}/mindmap/rebuild",
    response_model=AssetMindmapRebuildResponse,
    summary="重建资产导图",
)
def rebuild_asset_mindmap_endpoint(
    asset_id: str, db: Session = Depends(get_db)
) -> AssetMindmapRebuildResponse:
    """将当前资产推进到导图重建队列。"""
    asset, should_enqueue = enqueue_asset_mindmap_rebuild(db, asset_id)
    if should_enqueue:
        enqueue_generate_asset_mindmap.delay(asset.id)
    return AssetMindmapRebuildResponse(
        asset_id=asset.id,
        mindmap_status=asset.mindmap_status,
        message="已加入导图生成队列。"
        if should_enqueue
        else "当前资产导图正在生成中。",
    )


@router.post(
    "/{asset_id}/retrieval/search",
    response_model=AssetRetrievalSearchResponse,
    summary="按语义检索资产知识库",
)
def search_asset_retrieval_endpoint(
    asset_id: str,
    payload: AssetRetrievalSearchRequest,
    db: Session = Depends(get_db),
) -> AssetRetrievalSearchResponse:
    """返回单资产范围内可直接回跳的检索结果。"""
    return search_asset_chunks(
        db,
        asset_id=asset_id,
        query=payload.query,
        top_k=payload.top_k,
        rewrite_query=payload.rewrite_query,
        strategy=payload.strategy,
    )


@router.post(
    "/{asset_id}/chat/sessions",
    response_model=ChatSessionItem,
    summary="创建资产问答会话",
)
def create_asset_chat_session_endpoint(
    asset_id: str,
    payload: ChatSessionCreateRequest,
    db: Session = Depends(get_db),
) -> ChatSessionItem:
    """创建单资产问答会话。"""
    return create_asset_chat_session(
        db=db,
        asset_id=asset_id,
        user_id=settings.local_dev_user_id,
        payload=payload,
    )


@router.get(
    "/{asset_id}/chat/sessions",
    response_model=list[ChatSessionItem],
    summary="获取资产问答会话列表",
)
def list_asset_chat_sessions_endpoint(
    asset_id: str,
    db: Session = Depends(get_db),
) -> list[ChatSessionItem]:
    """返回当前资产下的会话列表。"""
    return list_asset_chat_sessions(db, asset_id)


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


@router.post(
    "/{asset_id}/notes",
    response_model=NoteItemResponse,
    summary="创建资产锚点笔记",
)
def create_asset_note_endpoint(
    asset_id: str,
    payload: CreateNoteRequest,
    db: Session = Depends(get_db),
) -> NoteItemResponse:
    """基于文本选区或导图节点锚点创建笔记。"""
    return create_asset_note(
        db=db,
        asset_id=asset_id,
        user_id=settings.local_dev_user_id,
        payload=payload,
    )


@router.get(
    "/{asset_id}/notes",
    response_model=NoteListResponse,
    summary="查询资产笔记列表",
)
def list_asset_notes_endpoint(
    asset_id: str,
    anchor_type: AnchorType | None = None,
    db: Session = Depends(get_db),
) -> NoteListResponse:
    """返回单资产范围下可用于复习和回跳的笔记列表。"""
    return list_asset_notes(
        db=db,
        asset_id=asset_id,
        user_id=settings.local_dev_user_id,
        anchor_type=anchor_type,
    )


@router.post(
    "/upload", response_model=AssetUploadResponse, summary="上传 PDF 并创建学习资产"
)
async def upload_asset_endpoint(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> AssetUploadResponse:
    """上传单个 PDF 文件，完成 OSS 存储与资产创建。"""
    content = await file.read()
    content_type = file.content_type or "application/pdf"

    validate_pdf_upload(
        filename=file.filename, content_type=content_type, content=content
    )
    return create_uploaded_asset(
        db=db,
        user_id=settings.local_dev_user_id,
        filename=file.filename or "paper.pdf",
        content_type=content_type,
        content=content,
        title=title,
    )
