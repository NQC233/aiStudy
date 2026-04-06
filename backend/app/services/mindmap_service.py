from __future__ import annotations

import json
import logging
import re
import socket
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.asset import Asset
from app.models.asset_file import AssetFile
from app.models.mindmap import Mindmap
from app.models.mindmap_node import MindmapNode
from app.schemas.mindmap import AssetMindmapResponse, MindmapNodeItem, MindmapSnapshot
from app.schemas.reader import (
    ParsedDocumentBlock,
    ParsedDocumentPayload,
    ParsedDocumentSection,
)

logger = logging.getLogger(__name__)

_SUMMARY_MAX_CHARS = 180
_TITLE_MAX_CHARS = 72
_SECTION_NODE_ORDER_STEP = 10
_KEYPOINT_NODE_LIMIT = 120
_KEYPOINT_PER_SECTION_LIMIT = 2
_STORY_EVIDENCE_PER_STAGE_LIMIT = 2

_STORY_STAGES: list[tuple[str, str]] = [
    ("problem", "问题背景"),
    ("method", "方法概览"),
    ("mechanism", "关键机制"),
    ("experiment", "实验结果"),
    ("conclusion", "结论与启发"),
]

_STAGE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "problem": (
        "introduction",
        "background",
        "motivation",
        "problem",
        "challenge",
        "问题",
        "背景",
        "动机",
    ),
    "method": (
        "method",
        "approach",
        "framework",
        "model",
        "algorithm",
        "方法",
        "方案",
        "模型",
        "算法",
    ),
    "mechanism": (
        "mechanism",
        "architecture",
        "module",
        "design",
        "implementation",
        "机制",
        "模块",
        "实现",
        "设计",
    ),
    "experiment": (
        "experiment",
        "evaluation",
        "result",
        "ablation",
        "benchmark",
        "实验",
        "评估",
        "结果",
        "消融",
    ),
    "conclusion": (
        "conclusion",
        "discussion",
        "limitation",
        "future",
        "结论",
        "局限",
        "讨论",
        "未来",
    ),
}


@dataclass
class GeneratedMindmapNode:
    node_key: str
    parent_key: str | None
    title: str
    summary: str | None
    level: int
    order: int
    page_no: int | None
    paragraph_ref: str | None
    section_path: list[str]
    block_ids: list[str]
    selector_payload: dict


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


def _next_mindmap_version(db: Session, asset_id: str) -> int:
    latest_version = db.scalar(
        select(func.max(Mindmap.version)).where(Mindmap.asset_id == asset_id)
    )
    return (latest_version or 0) + 1


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _truncate_text(text: str, max_chars: int) -> str:
    normalized = _normalize_text(text)
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max_chars - 1].rstrip()}..."


def _build_section_path(
    section: ParsedDocumentSection, section_map: dict[str, ParsedDocumentSection]
) -> list[str]:
    path: list[str] = []
    cursor = section
    visited: set[str] = set()
    while cursor.section_id not in visited:
        visited.add(cursor.section_id)
        title = _normalize_text(cursor.title) or "未命名章节"
        path.append(title)
        if cursor.parent_id is None:
            break
        next_section = section_map.get(cursor.parent_id)
        if next_section is None:
            break
        cursor = next_section
    path.reverse()
    return path


def _build_section_summary(
    section: ParsedDocumentSection,
    block_by_id: dict[str, ParsedDocumentBlock],
) -> str | None:
    text_blocks: list[str] = []
    for block_id in section.block_ids:
        block = block_by_id.get(block_id)
        if block is None:
            continue
        if block.type not in {"paragraph", "list", "heading", "equation", "code"}:
            continue
        text = _normalize_text(block.text)
        if not text:
            continue
        text_blocks.append(text)
        if len(text_blocks) >= 2:
            break
    if not text_blocks:
        return None
    return _truncate_text(" ".join(text_blocks), _SUMMARY_MAX_CHARS)


def _build_keypoint_title(block: ParsedDocumentBlock) -> str:
    text = _normalize_text(block.text)
    if not text:
        return "关键点"
    return _truncate_text(text, _TITLE_MAX_CHARS)


def _build_generated_nodes(
    payload: ParsedDocumentPayload,
) -> list[GeneratedMindmapNode]:
    section_map: dict[str, ParsedDocumentSection] = {
        section.section_id: section for section in payload.sections
    }
    block_by_id: dict[str, ParsedDocumentBlock] = {
        block.block_id: block for block in payload.blocks
    }
    blocks_by_section_id: dict[str, list[ParsedDocumentBlock]] = {}
    for block in sorted(payload.blocks, key=lambda item: item.order):
        blocks_by_section_id.setdefault(block.section_id, []).append(block)

    first_page = payload.pages[0].page_no if payload.pages else None
    root_title = _normalize_text(str(payload.document.get("title") or "")) or "论文导图"
    nodes: list[GeneratedMindmapNode] = [
        GeneratedMindmapNode(
            node_key="root",
            parent_key=None,
            title=root_title,
            summary=None,
            level=0,
            order=0,
            page_no=first_page,
            paragraph_ref=None,
            section_path=[],
            block_ids=[],
            selector_payload={"selector_type": "root", "node_type": "outline"},
        )
    ]

    ordered_sections = sorted(
        payload.sections,
        key=lambda item: (item.page_start, item.level, item.section_id),
    )
    section_node_key_by_id: dict[str, str] = {}
    section_order_seed = 1
    keypoint_count = 0

    for section in ordered_sections:
        section_title = _normalize_text(section.title) or "未命名章节"
        section_node_key = f"sec:{section.section_id}"
        section_node_key_by_id[section.section_id] = section_node_key

        parent_key = "root"
        if section.parent_id:
            parent_key = section_node_key_by_id.get(section.parent_id, "root")

        section_path = _build_section_path(section, section_map)
        primary_block_id = section.block_ids[0] if section.block_ids else None
        section_selector = {
            "selector_type": "section",
            "section_id": section.section_id,
        }
        if primary_block_id:
            section_selector = {
                "selector_type": "block",
                "block_id": primary_block_id,
                "node_type": "outline",
            }
        else:
            section_selector["node_type"] = "outline"

        nodes.append(
            GeneratedMindmapNode(
                node_key=section_node_key,
                parent_key=parent_key,
                title=section_title,
                summary=_build_section_summary(section, block_by_id),
                level=max(section.level, 1),
                order=section_order_seed * _SECTION_NODE_ORDER_STEP,
                page_no=section.page_start,
                paragraph_ref=None,
                section_path=section_path,
                block_ids=list(section.block_ids),
                selector_payload=section_selector,
            )
        )
        section_order_seed += 1

        if keypoint_count >= _KEYPOINT_NODE_LIMIT:
            continue

        keypoint_order = 1
        for block in blocks_by_section_id.get(section.section_id, []):
            if keypoint_order > _KEYPOINT_PER_SECTION_LIMIT:
                break
            if keypoint_count >= _KEYPOINT_NODE_LIMIT:
                break
            if block.type not in {"paragraph", "list", "equation", "code"}:
                continue
            normalized_text = _normalize_text(block.text)
            if not normalized_text:
                continue

            nodes.append(
                GeneratedMindmapNode(
                    node_key=f"kp:{block.block_id}",
                    parent_key=section_node_key,
                    title=_build_keypoint_title(block),
                    summary=_truncate_text(normalized_text, _SUMMARY_MAX_CHARS),
                    level=max(section.level + 1, 2),
                    order=(section_order_seed - 1) * _SECTION_NODE_ORDER_STEP
                    + keypoint_order,
                    page_no=block.page_no,
                    paragraph_ref=str(block.paragraph_no)
                    if block.paragraph_no is not None
                    else None,
                    section_path=section_path,
                    block_ids=[block.block_id],
                    selector_payload={
                        "selector_type": "block",
                        "block_id": block.block_id,
                        "node_type": "outline",
                    },
                )
            )
            keypoint_order += 1
            keypoint_count += 1

    _append_story_graph_nodes(
        nodes=nodes,
        sections=ordered_sections,
        blocks_by_section_id=blocks_by_section_id,
        section_map=section_map,
        block_by_id=block_by_id,
    )

    return nodes


def _pick_stage(section: ParsedDocumentSection, sample_text: str) -> str | None:
    haystack = (
        f"{_normalize_text(section.title)} {_normalize_text(sample_text)}".lower()
    )
    for stage, keywords in _STAGE_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return stage
    return None


def _append_story_graph_nodes(
    *,
    nodes: list[GeneratedMindmapNode],
    sections: list[ParsedDocumentSection],
    blocks_by_section_id: dict[str, list[ParsedDocumentBlock]],
    section_map: dict[str, ParsedDocumentSection],
    block_by_id: dict[str, ParsedDocumentBlock],
) -> None:
    stage_sections: dict[str, list[ParsedDocumentSection]] = {
        stage: [] for stage, _ in _STORY_STAGES
    }
    unassigned_sections = list(sections)

    for section in sections:
        sample_blocks = blocks_by_section_id.get(section.section_id, [])[:2]
        sample_text = " ".join(_normalize_text(block.text) for block in sample_blocks)
        stage = _pick_stage(section, sample_text)
        if stage is None:
            continue
        stage_sections[stage].append(section)
        if section in unassigned_sections:
            unassigned_sections.remove(section)

    for stage, _ in _STORY_STAGES:
        if stage_sections[stage] or not unassigned_sections:
            continue
        stage_sections[stage].append(unassigned_sections.pop(0))

    story_order_seed = 10000
    for stage, stage_label in _STORY_STAGES:
        assigned_sections = stage_sections.get(stage, [])
        if not assigned_sections:
            continue

        selected_blocks: list[ParsedDocumentBlock] = []
        for section in assigned_sections:
            for block in blocks_by_section_id.get(section.section_id, []):
                if block.type not in {
                    "paragraph",
                    "list",
                    "equation",
                    "code",
                    "heading",
                }:
                    continue
                if not _normalize_text(block.text):
                    continue
                selected_blocks.append(block)
                if len(selected_blocks) >= _STORY_EVIDENCE_PER_STAGE_LIMIT:
                    break
            if len(selected_blocks) >= _STORY_EVIDENCE_PER_STAGE_LIMIT:
                break

        if not selected_blocks:
            fallback_section = assigned_sections[0]
            for block_id in fallback_section.block_ids[
                :_STORY_EVIDENCE_PER_STAGE_LIMIT
            ]:
                block = block_by_id.get(block_id)
                if block is not None:
                    selected_blocks.append(block)

        stage_path = _build_section_path(assigned_sections[0], section_map)
        story_node_key = f"story:{stage}"
        story_summary_segments = [
            _truncate_text(_normalize_text(block.text), _SUMMARY_MAX_CHARS // 2)
            for block in selected_blocks
            if _normalize_text(block.text)
        ]
        story_summary = "；".join(
            segment for segment in story_summary_segments if segment
        )
        first_page = (
            selected_blocks[0].page_no
            if selected_blocks
            else assigned_sections[0].page_start
        )
        first_block_id = selected_blocks[0].block_id if selected_blocks else None

        nodes.append(
            GeneratedMindmapNode(
                node_key=story_node_key,
                parent_key="root",
                title=stage_label,
                summary=story_summary or None,
                level=1,
                order=story_order_seed,
                page_no=first_page,
                paragraph_ref=None,
                section_path=stage_path,
                block_ids=[block.block_id for block in selected_blocks],
                selector_payload={
                    "selector_type": "block" if first_block_id else "section",
                    "block_id": first_block_id,
                    "stage": stage,
                    "node_type": "story",
                },
            )
        )

        for index, block in enumerate(selected_blocks, start=1):
            nodes.append(
                GeneratedMindmapNode(
                    node_key=f"ev:{stage}:{block.block_id}",
                    parent_key=story_node_key,
                    title=f"证据 {index}",
                    summary=_truncate_text(
                        _normalize_text(block.text), _SUMMARY_MAX_CHARS
                    ),
                    level=2,
                    order=story_order_seed + index,
                    page_no=block.page_no,
                    paragraph_ref=str(block.paragraph_no)
                    if block.paragraph_no is not None
                    else None,
                    section_path=stage_path,
                    block_ids=[block.block_id],
                    selector_payload={
                        "selector_type": "block",
                        "block_id": block.block_id,
                        "stage": stage,
                        "node_type": "evidence",
                    },
                )
            )

        story_order_seed += 100


def _persist_nodes(
    db: Session, mindmap_id: str, nodes: list[GeneratedMindmapNode]
) -> None:
    node_model_by_key: dict[str, MindmapNode] = {}
    for node in nodes:
        model = MindmapNode(
            mindmap_id=mindmap_id,
            node_key=node.node_key,
            title=node.title,
            summary=node.summary,
            level=node.level,
            order=node.order,
            page_no=node.page_no,
            paragraph_ref=node.paragraph_ref,
            section_path=node.section_path,
            block_ids=node.block_ids,
            selector_payload=node.selector_payload,
        )
        db.add(model)
        node_model_by_key[node.node_key] = model

    db.flush()

    for node in nodes:
        if not node.parent_key:
            continue
        model = node_model_by_key.get(node.node_key)
        parent = node_model_by_key.get(node.parent_key)
        if model is None or parent is None:
            continue
        model.parent_id = parent.id


def _build_mindmap_snapshot(db: Session, mindmap: Mindmap) -> MindmapSnapshot:
    nodes = db.scalars(
        select(MindmapNode)
        .where(MindmapNode.mindmap_id == mindmap.id)
        .order_by(
            MindmapNode.level.asc(),
            MindmapNode.order.asc(),
            MindmapNode.created_at.asc(),
        )
    ).all()
    node_key_by_id = {item.id: item.node_key for item in nodes}
    payload_nodes = [
        MindmapNodeItem(
            id=item.id,
            parent_id=item.parent_id,
            node_key=item.node_key,
            parent_key=node_key_by_id.get(item.parent_id),
            title=item.title,
            summary=item.summary,
            level=item.level,
            order=item.order,
            page_no=item.page_no,
            paragraph_ref=item.paragraph_ref,
            section_path=item.section_path or [],
            block_ids=item.block_ids or [],
            selector_payload=item.selector_payload or {},
            node_type=str((item.selector_payload or {}).get("node_type") or "outline"),
            stage=(item.selector_payload or {}).get("stage"),
        )
        for item in nodes
    ]
    return MindmapSnapshot(
        id=mindmap.id,
        asset_id=mindmap.asset_id,
        version=mindmap.version,
        status=mindmap.status,
        root_node_key=(mindmap.meta or {}).get("root_node_key"),
        meta=mindmap.meta or {},
        created_at=mindmap.created_at,
        updated_at=mindmap.updated_at,
        nodes=payload_nodes,
    )


def _latest_mindmap(db: Session, asset_id: str) -> Mindmap | None:
    statement = (
        select(Mindmap)
        .where(Mindmap.asset_id == asset_id)
        .order_by(Mindmap.version.desc(), Mindmap.created_at.desc())
    )
    return db.scalars(statement).first()


def _latest_succeeded_mindmap(db: Session, asset_id: str) -> Mindmap | None:
    statement = (
        select(Mindmap)
        .where(Mindmap.asset_id == asset_id, Mindmap.status == "succeeded")
        .order_by(Mindmap.version.desc(), Mindmap.created_at.desc())
    )
    return db.scalars(statement).first()


def get_asset_mindmap(db: Session, asset_id: str) -> AssetMindmapResponse:
    asset = _require_asset(db, asset_id)
    latest = _latest_mindmap(db, asset_id)
    if latest is None:
        return AssetMindmapResponse(
            asset_id=asset.id, mindmap_status=asset.mindmap_status, mindmap=None
        )

    selected = latest
    if latest.status != "succeeded":
        fallback = _latest_succeeded_mindmap(db, asset_id)
        if fallback is not None:
            selected = fallback

    return AssetMindmapResponse(
        asset_id=asset.id,
        mindmap_status=asset.mindmap_status,
        mindmap=_build_mindmap_snapshot(db, selected),
    )


def enqueue_asset_mindmap_rebuild(db: Session, asset_id: str) -> tuple[Asset, bool]:
    asset = _require_asset(db, asset_id)
    if asset.parse_status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前资产解析尚未完成，暂时无法生成导图。",
        )

    if asset.mindmap_status == "processing":
        return asset, False

    asset.mindmap_status = "processing"
    db.commit()
    db.refresh(asset)
    return asset, True


def run_asset_mindmap_pipeline(
    db: Session,
    asset_id: str,
    retry_meta: dict[str, str | int | bool | None] | None = None,
) -> dict[str, str | int]:
    """基于 parsed_json 生成导图并持久化节点映射。"""
    asset = _require_asset(db, asset_id)
    if asset.parse_status != "ready":
        raise RuntimeError("当前资产解析尚未完成，无法生成导图。")

    version = _next_mindmap_version(db, asset_id)
    asset.mindmap_status = "processing"
    mindmap = Mindmap(
        asset_id=asset_id,
        version=version,
        status="running",
        meta={
            "generator": "parsed_json_v1",
            "root_node_key": "root",
        },
    )
    db.add(mindmap)
    db.commit()
    db.refresh(mindmap)

    try:
        payload = _load_parsed_payload(db, asset_id)
        nodes = _build_generated_nodes(payload)
        _persist_nodes(db, mindmap.id, nodes)
        mindmap.status = "succeeded"
        mindmap.meta = {
            **(mindmap.meta or {}),
            "parse_id": payload.parse_id,
            "node_count": len(nodes),
        }
        asset = _require_asset(db, asset_id)
        asset.mindmap_status = "ready"
        db.commit()
        db.refresh(mindmap)
        return {
            "asset_id": asset_id,
            "mindmap_id": mindmap.id,
            "version": mindmap.version,
            "mindmap_status": "ready",
            "node_count": len(nodes),
        }
    except Exception as exc:
        db.rollback()
        db_asset = _require_asset(db, asset_id)
        db_mindmap = db.get(Mindmap, mindmap.id)
        if db_mindmap is not None:
            db_mindmap.status = "failed"
            db_mindmap.meta = {
                **(db_mindmap.meta or {}),
                "failure_reason": str(exc)[:500],
                "retry": retry_meta or {},
            }
        db_asset.mindmap_status = "failed"
        db.commit()
        logger.exception("资产导图生成失败: asset_id=%s", asset_id, exc_info=exc)
        raise
