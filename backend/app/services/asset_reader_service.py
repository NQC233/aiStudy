from __future__ import annotations

import json
import re
import socket
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.asset_file import AssetFile
from app.services.asset_service import require_user_asset
from app.core.config import settings
from app.services.oss_service import OSSConfigurationError, build_parse_artifact_key, build_public_url
from app.schemas.anchor import AssetAnchorPreviewRequest, AssetAnchorPreviewResponse
from app.schemas.reader import AssetParsedDocumentResponse, AssetPdfDescriptor, ParsedDocumentPayload


def _get_latest_asset_file(db: Session, asset_id: str, file_type: str) -> AssetFile | None:
    statement = (
        select(AssetFile)
        .where(AssetFile.asset_id == asset_id, AssetFile.file_type == file_type)
        .order_by(AssetFile.created_at.desc())
    )
    return db.scalars(statement).first()


def _require_asset(db: Session, asset_id: str) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到对应的学习资产。")
    return asset


def _download_bytes(public_url: str) -> tuple[bytes, str | None]:
    try:
        with urlopen(public_url, timeout=settings.remote_file_fetch_timeout_sec) as response:
            return response.read(), response.headers.get_content_type()
    except HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"读取远端文件失败：{exc.code}",
        ) from exc
    except (TimeoutError, socket.timeout):
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="读取远端文件超时，请检查 OSS/外链可用性。",
        ) from None
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="读取远端文件超时，请检查 OSS/外链可用性。",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="读取远端文件失败，当前文件地址不可达。",
        ) from exc


def get_asset_pdf_descriptor(db: Session, asset_id: str, user_id: str) -> AssetPdfDescriptor:
    require_user_asset(db, asset_id, user_id)
    asset_file = _get_latest_asset_file(db, asset_id, "original_pdf")
    if asset_file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前资产缺少原始 PDF。")

    return AssetPdfDescriptor(
        asset_id=asset_id,
        file_id=asset_file.id,
        file_type=asset_file.file_type,
        mime_type=asset_file.mime_type,
        size=asset_file.size,
        url=asset_file.public_url,
    )


def get_asset_pdf_content(db: Session, asset_id: str, user_id: str) -> tuple[bytes, str]:
    descriptor = get_asset_pdf_descriptor(db, asset_id, user_id)
    content, remote_content_type = _download_bytes(descriptor.url)
    return content, remote_content_type or descriptor.mime_type or "application/pdf"


def _resource_public_url(
    user_id: str,
    asset_id: str,
    parse_id: str,
    path: str | None,
) -> str | None:
    if not path:
        return None

    normalized_path = path.strip()
    if not normalized_path:
        return None

    if normalized_path.startswith("http://") or normalized_path.startswith("https://"):
        return normalized_path

    normalized_path = normalized_path.replace("\\", "/").lstrip("./").lstrip("/")
    storage_key = build_parse_artifact_key(
        user_id=user_id,
        asset_id=asset_id,
        parse_id=parse_id,
        relative_path=f"raw/extracted/{normalized_path}",
    )
    try:
        return build_public_url(storage_key)
    except OSSConfigurationError:
        return None


def _enrich_resource_urls(payload: ParsedDocumentPayload, asset: Asset) -> None:
    parse_id = payload.parse_id
    if not parse_id:
        return

    resource_url_by_id: dict[str, str] = {}
    for group in (payload.assets.images, payload.assets.tables):
        for resource in group:
            resource_id = str(resource.get("resource_id") or "")
            public_url = _resource_public_url(
                user_id=asset.user_id,
                asset_id=asset.id,
                parse_id=parse_id,
                path=resource.get("path"),
            )
            if public_url:
                resource["public_url"] = public_url
                if resource_id:
                    resource_url_by_id[resource_id] = public_url

    for block in payload.blocks:
        if not block.resource_ref:
            continue
        public_url = resource_url_by_id.get(block.resource_ref)
        if not public_url:
            continue
        block.metadata = {
            **(block.metadata or {}),
            "resource_url": public_url,
        }


def _looks_like_resource_caption(text: str, resource_type: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    if resource_type == "image":
        return bool(re.match(r"^(fig(?:ure)?\.?\s*\d+|图\s*\d+)", normalized))
    if resource_type == "table":
        return bool(re.match(r"^(table\.?\s*\d+|表\s*\d+)", normalized))
    return False


def _enrich_resource_captions(payload: ParsedDocumentPayload) -> None:
    blocks = sorted(payload.blocks, key=lambda block: block.order)
    block_by_id = {block.block_id: block for block in blocks}

    for group in (payload.assets.images, payload.assets.tables):
        for resource in group:
            if resource.get("caption"):
                continue

            resource_type = str(resource.get("type") or "")
            parent_block_id = str(resource.get("block_id") or "")
            parent_block = block_by_id.get(parent_block_id)
            if parent_block is None:
                continue

            candidate_caption = None
            for block in blocks:
                if block.order <= parent_block.order:
                    continue
                if block.page_no != parent_block.page_no:
                    break
                if block.type in {"image", "table"}:
                    break
                text = (block.text or "").strip()
                if text and _looks_like_resource_caption(text, resource_type):
                    candidate_caption = text
                    break

            if not candidate_caption:
                continue

            resource["caption"] = [candidate_caption]
            parent_block.metadata = {
                **(parent_block.metadata or {}),
                "caption": [candidate_caption],
            }
            if not parent_block.text:
                parent_block.text = candidate_caption


def get_asset_parsed_document(db: Session, asset_id: str, user_id: str) -> AssetParsedDocumentResponse:
    asset = require_user_asset(db, asset_id, user_id)
    asset_file = _get_latest_asset_file(db, asset_id, "parsed_json")
    if asset_file is None:
        return AssetParsedDocumentResponse(asset_id=asset_id, parse_status=asset.parse_status)

    content, _ = _download_bytes(asset_file.public_url)
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="解析结果文件不是合法的 JSON。",
        ) from exc

    parsed_payload = ParsedDocumentPayload.model_validate(payload)
    _enrich_resource_urls(parsed_payload, asset)
    _enrich_resource_captions(parsed_payload)
    return AssetParsedDocumentResponse(
        asset_id=asset_id,
        parse_status=asset.parse_status,
        parse_id=parsed_payload.parse_id,
        parsed_json=parsed_payload,
    )


def preview_asset_anchor(
    db: Session,
    asset_id: str,
    user_id: str,
    payload: AssetAnchorPreviewRequest,
) -> AssetAnchorPreviewResponse:
    parsed_document = get_asset_parsed_document(db, asset_id, user_id)
    parsed_json = parsed_document.parsed_json
    if parsed_json is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前资产还没有可用的 parsed_json，暂时无法生成锚点。",
        )

    block_by_id = {block.block_id: block for block in parsed_json.blocks}
    page_blocks = [block for block in parsed_json.blocks if block.page_no == payload.page_no]
    if not page_blocks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前页缺少块级信息，无法生成锚点。",
        )

    selected_block = None
    if payload.block_id:
        selected_block = block_by_id.get(payload.block_id)
        if selected_block is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="block_id 不存在。")
        if selected_block.page_no != payload.page_no:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="block_id 与 page_no 不匹配。")
    else:
        selected_block = page_blocks[0]

    normalized_text = payload.selected_text.strip()
    if not normalized_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="selected_text 不能为空。")

    paragraph_no = payload.paragraph_no or selected_block.paragraph_no
    selector_payload = {
        "block_id": selected_block.block_id,
        **payload.selector_payload,
    }

    return AssetAnchorPreviewResponse(
        asset_id=asset_id,
        page_no=payload.page_no,
        block_id=selected_block.block_id,
        paragraph_no=paragraph_no,
        selected_text=normalized_text,
        selector_type="block",
        selector_payload=selector_payload,
    )
