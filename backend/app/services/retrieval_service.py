from __future__ import annotations

import json
import logging
import socket
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.asset import Asset
from app.models.asset_file import AssetFile
from app.models.document_chunk import DocumentChunk
from app.models.document_parse import DocumentParse
from app.schemas.document_chunk import (
    AssetChunkListResponse,
    AssetRetrievalSearchResponse,
    RetrievalSearchHit,
)
from app.schemas.reader import ParsedDocumentPayload
from app.services.chunk_builder_service import (
    ChunkBuildResult,
    build_chunks_from_parsed_payload,
)
from app.services.embedding_service import (
    EmbeddingConfigurationError,
    EmbeddingRequestError,
    embed_texts,
)

logger = logging.getLogger(__name__)


def _require_asset(db: Session, asset_id: str) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="未找到对应的学习资产。"
        )
    return asset


def _get_latest_asset_file(
    db: Session, asset_id: str, file_type: str
) -> AssetFile | None:
    statement = (
        select(AssetFile)
        .where(AssetFile.asset_id == asset_id, AssetFile.file_type == file_type)
        .order_by(AssetFile.created_at.desc())
    )
    return db.scalars(statement).first()


def _get_latest_succeeded_parse(db: Session, asset_id: str) -> DocumentParse | None:
    statement = (
        select(DocumentParse)
        .where(DocumentParse.asset_id == asset_id, DocumentParse.status == "succeeded")
        .order_by(DocumentParse.created_at.desc())
    )
    return db.scalars(statement).first()


def _download_bytes(public_url: str) -> bytes:
    try:
        with urlopen(
            public_url, timeout=settings.remote_file_fetch_timeout_sec
        ) as response:
            return response.read()
    except HTTPError as exc:
        raise RuntimeError(f"读取 parsed_json 失败：HTTP {exc.code}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise RuntimeError("读取 parsed_json 超时，请检查 OSS/外链可用性。") from exc
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise RuntimeError(
                "读取 parsed_json 超时，请检查 OSS/外链可用性。"
            ) from exc
        raise RuntimeError("读取 parsed_json 失败：远端地址不可达。") from exc


def _load_parsed_payload(db: Session, asset_id: str) -> ParsedDocumentPayload:
    parsed_json_file = _get_latest_asset_file(db, asset_id, "parsed_json")
    if parsed_json_file is None:
        raise RuntimeError("当前资产缺少 parsed_json 文件。")

    raw_bytes = _download_bytes(parsed_json_file.public_url)
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("parsed_json 文件内容不是合法 JSON。") from exc
    return ParsedDocumentPayload.model_validate(payload)


def _replace_chunks(
    db: Session,
    asset_id: str,
    parse_id: str,
    chunks: list[ChunkBuildResult],
) -> None:
    db.execute(delete(DocumentChunk).where(DocumentChunk.asset_id == asset_id))
    for chunk in chunks:
        db.add(
            DocumentChunk(
                asset_id=asset_id,
                parse_id=parse_id,
                chunk_index=chunk.chunk_index,
                section_path=chunk.section_path,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                paragraph_start=chunk.paragraph_start,
                paragraph_end=chunk.paragraph_end,
                block_ids=chunk.block_ids,
                text_content=chunk.text_content,
                token_count=chunk.token_count,
                embedding_status="not_started",
            )
        )
    db.commit()


def _embed_all_chunks(db: Session, asset_id: str) -> int:
    statement = (
        select(DocumentChunk)
        .where(DocumentChunk.asset_id == asset_id)
        .order_by(DocumentChunk.chunk_index.asc())
    )
    chunks = db.scalars(statement).all()
    if not chunks:
        return 0

    for chunk in chunks:
        chunk.embedding_status = "processing"
    db.commit()

    texts = [chunk.text_content for chunk in chunks]
    embeddings = embed_texts(texts, text_type="document")

    for chunk, embedding in zip(chunks, embeddings, strict=True):
        chunk.embedding = embedding
        chunk.embedding_status = "ready"
    db.commit()
    return len(chunks)


def list_asset_chunks(
    db: Session, asset_id: str, limit: int = 100
) -> AssetChunkListResponse:
    asset = _require_asset(db, asset_id)
    safe_limit = max(1, min(limit, 500))
    total_count = (
        db.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.asset_id == asset_id)
        )
        or 0
    )

    statement = (
        select(DocumentChunk)
        .where(DocumentChunk.asset_id == asset_id)
        .order_by(DocumentChunk.chunk_index.asc())
        .limit(safe_limit)
    )
    chunks = db.scalars(statement).all()
    parse_id = chunks[0].parse_id if chunks else None
    return AssetChunkListResponse(
        asset_id=asset.id,
        kb_status=asset.kb_status,
        parse_id=parse_id,
        total_count=total_count,
        chunks=chunks,
    )


def enqueue_asset_chunk_rebuild(db: Session, asset_id: str) -> tuple[Asset, bool]:
    asset = _require_asset(db, asset_id)
    if asset.parse_status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前资产解析尚未完成，暂时无法构建知识库。",
        )

    if asset.kb_status == "processing":
        return asset, False

    asset.kb_status = "processing"
    db.commit()
    db.refresh(asset)
    return asset, True


def run_asset_kb_pipeline(
    db: Session,
    asset_id: str,
    retry_meta: dict[str, str | int | bool | None] | None = None,
) -> dict[str, str | int | None]:
    """执行 document_chunks 构建和向量化。"""
    asset = _require_asset(db, asset_id)
    latest_parse = _get_latest_succeeded_parse(db, asset_id)
    if latest_parse is None:
        raise RuntimeError("当前资产没有可用的成功解析记录，无法构建知识库。")

    asset.kb_status = "processing"
    db.commit()

    try:
        payload = _load_parsed_payload(db, asset_id)
        built_chunks = build_chunks_from_parsed_payload(payload)
        parse_id = payload.parse_id or latest_parse.id
        _replace_chunks(db, asset_id=asset_id, parse_id=parse_id, chunks=built_chunks)
        chunk_count = _embed_all_chunks(db, asset_id=asset_id)
        asset.kb_status = "ready"
        db.commit()
        return {
            "asset_id": asset.id,
            "parse_id": parse_id,
            "kb_status": asset.kb_status,
            "chunk_count": chunk_count,
        }
    except Exception as exc:
        db.rollback()
        asset = _require_asset(db, asset_id)
        statement = select(DocumentChunk).where(
            DocumentChunk.asset_id == asset_id,
            DocumentChunk.embedding_status.in_(["processing", "not_started"]),
        )
        for chunk in db.scalars(statement).all():
            chunk.embedding_status = "failed"
        asset.kb_status = "failed"
        db.commit()
        logger.exception(
            "资产知识库构建失败: asset_id=%s retry_meta=%s",
            asset_id,
            retry_meta,
            exc_info=exc,
        )
        raise


def search_asset_chunks(
    db: Session,
    asset_id: str,
    query: str,
    top_k: int,
) -> AssetRetrievalSearchResponse:
    _require_asset(db, asset_id)
    normalized_query = query.strip()
    if not normalized_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="query 不能为空。"
        )

    try:
        query_embeddings = embed_texts([normalized_query], text_type="query")
    except (EmbeddingConfigurationError, EmbeddingRequestError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"向量服务暂不可用：{exc}",
        ) from exc

    if not query_embeddings:
        return AssetRetrievalSearchResponse(
            asset_id=asset_id, query=normalized_query, top_k=top_k, results=[]
        )
    query_embedding = query_embeddings[0]

    distance = DocumentChunk.embedding.cosine_distance(query_embedding).label(
        "distance"
    )
    statement = (
        select(DocumentChunk, distance)
        .where(
            DocumentChunk.asset_id == asset_id,
            DocumentChunk.embedding_status == "ready",
            DocumentChunk.embedding.is_not(None),
        )
        .order_by(distance.asc())
        .limit(top_k)
    )
    rows = db.execute(statement).all()

    results: list[RetrievalSearchHit] = []
    for chunk, chunk_distance in rows:
        distance_value = float(chunk_distance) if chunk_distance is not None else 1.0
        quote_text = chunk.text_content[:220].strip()
        if len(chunk.text_content) > 220:
            quote_text = f"{quote_text}..."
        results.append(
            RetrievalSearchHit(
                chunk_id=chunk.id,
                score=max(0.0, 1.0 - distance_value),
                text=chunk.text_content,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                paragraph_start=chunk.paragraph_start,
                paragraph_end=chunk.paragraph_end,
                block_ids=chunk.block_ids or [],
                section_path=chunk.section_path or [],
                quote_text=quote_text,
            )
        )

    return AssetRetrievalSearchResponse(
        asset_id=asset_id, query=normalized_query, top_k=top_k, results=results
    )
