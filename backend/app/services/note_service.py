from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.anchor import Anchor
from app.models.asset import Asset
from app.models.mindmap import Mindmap
from app.models.mindmap_node import MindmapNode
from app.models.note import Note
from app.schemas.note import (
    AnchorType,
    CreateNoteRequest,
    NoteAnchorItem,
    NoteAnchorPayload,
    NoteDeleteResponse,
    NoteItemResponse,
    NoteListResponse,
    UpdateNoteRequest,
)
from app.services.asset_reader_service import get_asset_parsed_document


def _require_asset(db: Session, asset_id: str) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到对应的学习资产。")
    return asset


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_text_selection_anchor(
    db: Session,
    asset_id: str,
    payload: NoteAnchorPayload,
) -> dict[str, Any]:
    selector_payload = dict(payload.selector_payload or {})
    raw_block_id = payload.block_id or selector_payload.get("block_id")
    block_id = str(raw_block_id).strip() if raw_block_id is not None else None
    if not block_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="text_selection 锚点必须包含 block_id 或 selector_payload.block_id。",
        )

    parsed_document = get_asset_parsed_document(db, asset_id)
    parsed_json = parsed_document.parsed_json
    if parsed_json is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前资产还没有可用的 parsed_json，暂时无法校验文本锚点。",
        )

    block_by_id = {block.block_id: block for block in parsed_json.blocks}
    selected_block = block_by_id.get(block_id)
    if selected_block is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="text_selection 锚点中的 block_id 不存在。")

    if payload.page_no is not None and payload.page_no != selected_block.page_no:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="text_selection 锚点中的 page_no 与 block_id 不匹配。",
        )

    selector_type = (payload.selector_type or "block").strip() or "block"
    # 统一把 block_id 强制写回 selector_payload，避免后续回跳时出现字段缺失。
    normalized_selector_payload = {
        **selector_payload,
        "block_id": selected_block.block_id,
    }
    return {
        "anchor_type": "text_selection",
        "page_no": selected_block.page_no,
        "block_id": selected_block.block_id,
        "paragraph_no": payload.paragraph_no or selected_block.paragraph_no,
        "selected_text": _normalize_optional_text(payload.selected_text),
        "selector_type": selector_type,
        "selector_payload": normalized_selector_payload,
    }


def _normalize_mindmap_node_anchor(
    db: Session,
    asset_id: str,
    payload: NoteAnchorPayload,
) -> dict[str, Any]:
    selector_payload = dict(payload.selector_payload or {})
    raw_node_key = selector_payload.get("node_key")
    node_key = str(raw_node_key).strip() if raw_node_key is not None else ""
    if not node_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mindmap_node 锚点必须包含 selector_payload.node_key。",
        )

    statement = (
        select(MindmapNode)
        .join(Mindmap, Mindmap.id == MindmapNode.mindmap_id)
        .where(Mindmap.asset_id == asset_id, MindmapNode.node_key == node_key)
        .order_by(Mindmap.version.desc(), Mindmap.created_at.desc(), MindmapNode.created_at.desc())
    )
    mindmap_node = db.scalars(statement).first()
    if mindmap_node is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mindmap_node 锚点中的 node_key 不存在或不属于当前资产。",
        )

    normalized_block_id = _normalize_optional_text(payload.block_id) or (mindmap_node.block_ids[0] if mindmap_node.block_ids else None)
    if normalized_block_id and mindmap_node.block_ids and normalized_block_id not in mindmap_node.block_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mindmap_node 锚点中的 block_id 与节点映射不一致。",
        )

    if payload.page_no is not None and mindmap_node.page_no is not None and payload.page_no != mindmap_node.page_no:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mindmap_node 锚点中的 page_no 与节点映射不一致。",
        )

    normalized_selector_payload = {
        **selector_payload,
        "node_key": mindmap_node.node_key,
        "node_id": mindmap_node.id,
        "mindmap_id": mindmap_node.mindmap_id,
    }
    if normalized_block_id:
        normalized_selector_payload["block_id"] = normalized_block_id

    return {
        "anchor_type": "mindmap_node",
        "page_no": payload.page_no or mindmap_node.page_no,
        "block_id": normalized_block_id,
        "paragraph_no": payload.paragraph_no,
        "selected_text": _normalize_optional_text(payload.selected_text),
        "selector_type": "mindmap_node",
        "selector_payload": normalized_selector_payload,
    }


def _normalize_knowledge_point_anchor(payload: NoteAnchorPayload) -> dict[str, Any]:
    selector_payload = dict(payload.selector_payload or {})
    normalized_block_id = _normalize_optional_text(payload.block_id)
    if not selector_payload and not normalized_block_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="knowledge_point 锚点至少需要 selector_payload 或 block_id。",
        )
    if normalized_block_id:
        selector_payload = {
            **selector_payload,
            "block_id": normalized_block_id,
        }

    selector_type = (payload.selector_type or "knowledge_point").strip() or "knowledge_point"
    return {
        "anchor_type": "knowledge_point",
        "page_no": payload.page_no,
        "block_id": normalized_block_id,
        "paragraph_no": payload.paragraph_no,
        "selected_text": _normalize_optional_text(payload.selected_text),
        "selector_type": selector_type,
        "selector_payload": selector_payload,
    }


def _normalize_anchor_payload(
    db: Session,
    asset_id: str,
    payload: NoteAnchorPayload,
) -> dict[str, Any]:
    # 关键归一化逻辑：把不同来源的锚点结构统一为可持久化、可回跳的稳定字段集合。
    if payload.anchor_type == "text_selection":
        return _normalize_text_selection_anchor(db, asset_id, payload)
    if payload.anchor_type == "mindmap_node":
        return _normalize_mindmap_node_anchor(db, asset_id, payload)
    return _normalize_knowledge_point_anchor(payload)


def _get_existing_anchor(
    db: Session,
    asset_id: str,
    user_id: str,
    normalized_anchor: dict[str, Any],
) -> Anchor | None:
    statement = (
        select(Anchor)
        .where(
            Anchor.asset_id == asset_id,
            Anchor.user_id == user_id,
            Anchor.anchor_type == normalized_anchor["anchor_type"],
            Anchor.page_no == normalized_anchor["page_no"],
            Anchor.block_id == normalized_anchor["block_id"],
            Anchor.paragraph_no == normalized_anchor["paragraph_no"],
            Anchor.selected_text == normalized_anchor["selected_text"],
            Anchor.selector_type == normalized_anchor["selector_type"],
            Anchor.selector_payload == normalized_anchor["selector_payload"],
        )
        .order_by(Anchor.created_at.desc())
    )
    return db.scalars(statement).first()


def _get_or_create_anchor(
    db: Session,
    asset_id: str,
    user_id: str,
    normalized_anchor: dict[str, Any],
) -> Anchor:
    existing = _get_existing_anchor(db, asset_id=asset_id, user_id=user_id, normalized_anchor=normalized_anchor)
    if existing is not None:
        return existing

    anchor = Anchor(
        asset_id=asset_id,
        user_id=user_id,
        anchor_type=normalized_anchor["anchor_type"],
        page_no=normalized_anchor["page_no"],
        block_id=normalized_anchor["block_id"],
        paragraph_no=normalized_anchor["paragraph_no"],
        selected_text=normalized_anchor["selected_text"],
        selector_type=normalized_anchor["selector_type"],
        selector_payload=normalized_anchor["selector_payload"],
    )
    db.add(anchor)
    db.flush()
    return anchor


def _to_note_item(note: Note) -> NoteItemResponse:
    anchor = note.anchor
    if anchor is None:
        raise RuntimeError(f"笔记缺少 anchor 关系: note_id={note.id}")

    return NoteItemResponse(
        id=note.id,
        asset_id=note.asset_id,
        user_id=note.user_id,
        title=note.title,
        content=note.content,
        anchor=NoteAnchorItem(
            id=anchor.id,
            anchor_type=anchor.anchor_type,  # type: ignore[arg-type]
            page_no=anchor.page_no,
            block_id=anchor.block_id,
            paragraph_no=anchor.paragraph_no,
            selected_text=anchor.selected_text,
            selector_type=anchor.selector_type,
            selector_payload=anchor.selector_payload or {},
            created_at=anchor.created_at,
        ),
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


def _load_note_with_anchor(db: Session, note_id: str) -> Note | None:
    statement = (
        select(Note)
        .options(selectinload(Note.anchor))
        .where(Note.id == note_id)
    )
    return db.scalars(statement).first()


def _require_user_note(db: Session, note_id: str, user_id: str) -> Note:
    statement = (
        select(Note)
        .options(selectinload(Note.anchor))
        .where(Note.id == note_id, Note.user_id == user_id)
    )
    note = db.scalars(statement).first()
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到对应的笔记。")
    return note


def create_asset_note(
    db: Session,
    asset_id: str,
    user_id: str,
    payload: CreateNoteRequest,
) -> NoteItemResponse:
    asset = _require_asset(db, asset_id)
    normalized_anchor = _normalize_anchor_payload(db, asset.id, payload.anchor)
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="content 不能为空。")

    note = Note(
        asset_id=asset.id,
        user_id=user_id,
        anchor_id=_get_or_create_anchor(
            db,
            asset_id=asset.id,
            user_id=user_id,
            normalized_anchor=normalized_anchor,
        ).id,
        title=_normalize_optional_text(payload.title),
        content=content,
    )
    db.add(note)
    db.commit()

    saved_note = _load_note_with_anchor(db, note.id)
    if saved_note is None:
        raise RuntimeError(f"创建笔记后查询失败: note_id={note.id}")
    return _to_note_item(saved_note)


def list_asset_notes(
    db: Session,
    asset_id: str,
    user_id: str,
    anchor_type: AnchorType | None = None,
) -> NoteListResponse:
    _require_asset(db, asset_id)
    statement = (
        select(Note)
        .options(selectinload(Note.anchor))
        .where(Note.asset_id == asset_id, Note.user_id == user_id)
        .order_by(Note.created_at.desc())
    )
    notes = db.scalars(statement).all()
    note_items: list[NoteItemResponse] = []
    for note in notes:
        if note.anchor is None:
            continue
        if anchor_type is not None and note.anchor.anchor_type != anchor_type:
            continue
        note_items.append(_to_note_item(note))

    return NoteListResponse(
        asset_id=asset_id,
        total=len(note_items),
        anchor_type=anchor_type,
        notes=note_items,
    )


def update_note(
    db: Session,
    note_id: str,
    user_id: str,
    payload: UpdateNoteRequest,
) -> NoteItemResponse:
    note = _require_user_note(db, note_id, user_id)

    if payload.title is not None:
        note.title = _normalize_optional_text(payload.title)
    if payload.content is not None:
        content = payload.content.strip()
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="content 不能为空。")
        note.content = content

    db.commit()
    db.refresh(note)

    refreshed_note = _load_note_with_anchor(db, note.id)
    if refreshed_note is None:
        raise RuntimeError(f"更新笔记后查询失败: note_id={note.id}")
    return _to_note_item(refreshed_note)


def delete_note(
    db: Session,
    note_id: str,
    user_id: str,
) -> NoteDeleteResponse:
    note = _require_user_note(db, note_id, user_id)
    db.delete(note)
    db.commit()
    return NoteDeleteResponse(note_id=note_id, deleted=True)
