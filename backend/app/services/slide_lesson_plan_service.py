from __future__ import annotations

import json
import logging
import re
import socket
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.asset import Asset
from app.models.asset_file import AssetFile
from app.models.mindmap import Mindmap
from app.models.mindmap_node import MindmapNode
from app.models.presentation import Presentation
from app.schemas.reader import (
    ParsedDocumentBlock,
    ParsedDocumentPayload,
    ParsedDocumentSection,
)
from app.schemas.slide_lesson_plan import (
    AssetLessonPlanPayload,
    AssetLessonPlanRebuildResponse,
    AssetLessonPlanResponse,
    LessonPlanEvidenceAnchor,
    LessonPlanStage,
    LessonPlanStageSummary,
    PresentationSnapshot,
)

logger = logging.getLogger(__name__)

LESSON_PLAN_PLACEHOLDER_SCRIPT = "【讲稿占位】本阶段讲解将在 Spec 11B/11C 完善。"

_STAGES: list[tuple[str, str, tuple[str, ...]]] = [
    (
        "problem",
        "问题背景",
        (
            "introduction",
            "background",
            "motivation",
            "problem",
            "challenge",
            "问题",
            "背景",
            "动机",
        ),
    ),
    (
        "method",
        "方法概览",
        (
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
    ),
    (
        "mechanism",
        "关键机制",
        (
            "mechanism",
            "architecture",
            "module",
            "design",
            "implementation",
            "机制",
            "模块",
            "设计",
            "实现",
        ),
    ),
    (
        "experiment",
        "实验结果",
        (
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
    ),
    (
        "conclusion",
        "结论与启发",
        (
            "conclusion",
            "discussion",
            "limitation",
            "future",
            "结论",
            "讨论",
            "局限",
            "未来",
        ),
    ),
]


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _truncate(value: str, max_chars: int = 180) -> str:
    normalized = _normalize_text(value)
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max_chars - 1].rstrip()}..."


def _require_asset(db: Session, asset_id: str) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到对应的学习资产。",
        )
    return asset


def can_enqueue_lesson_plan_rebuild(
    parse_status: str,
    slides_status: str,
) -> tuple[bool, str]:
    if parse_status != "ready":
        return False, "parse_not_ready"
    if slides_status == "processing":
        return False, "already_processing"
    return True, "ok"


def is_slides_processing_stale(
    updated_at: datetime | None,
    now: datetime,
    stale_after_seconds: int,
) -> bool:
    if updated_at is None:
        return False
    safe_timeout = max(stale_after_seconds, 1)
    return updated_at <= now - timedelta(seconds=safe_timeout)


def _latest_asset_file(db: Session, asset_id: str, file_type: str) -> AssetFile | None:
    return db.scalars(
        select(AssetFile)
        .where(AssetFile.asset_id == asset_id, AssetFile.file_type == file_type)
        .order_by(AssetFile.created_at.desc())
    ).first()


def _download_bytes(public_url: str) -> bytes:
    try:
        with urlopen(
            public_url, timeout=settings.remote_file_fetch_timeout_sec
        ) as response:
            return response.read()
    except HTTPError as exc:
        raise RuntimeError(f"读取 lesson_plan 输入失败：HTTP {exc.code}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise RuntimeError(
            "读取 lesson_plan 输入超时，请检查 OSS/外链可用性。"
        ) from exc
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise RuntimeError(
                "读取 lesson_plan 输入超时，请检查 OSS/外链可用性。"
            ) from exc
        raise RuntimeError("读取 lesson_plan 输入失败：远端地址不可达。") from exc


def _load_parsed_payload(db: Session, asset_id: str) -> ParsedDocumentPayload:
    parsed_json_file = _latest_asset_file(db, asset_id, "parsed_json")
    if parsed_json_file is None:
        raise RuntimeError("当前资产缺少 parsed_json 文件。")
    raw_bytes = _download_bytes(parsed_json_file.public_url)
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("parsed_json 文件内容不是合法 JSON。") from exc
    return ParsedDocumentPayload.model_validate(payload)


def _load_story_evidence(
    db: Session, asset_id: str
) -> dict[str, list[LessonPlanEvidenceAnchor]]:
    latest_mindmap = db.scalars(
        select(Mindmap)
        .where(Mindmap.asset_id == asset_id, Mindmap.status == "succeeded")
        .order_by(Mindmap.version.desc(), Mindmap.created_at.desc())
    ).first()
    if latest_mindmap is None:
        return {}

    evidence_nodes = db.scalars(
        select(MindmapNode)
        .where(MindmapNode.mindmap_id == latest_mindmap.id)
        .order_by(MindmapNode.order.asc(), MindmapNode.created_at.asc())
    ).all()

    stage_map: dict[str, list[LessonPlanEvidenceAnchor]] = {}
    for node in evidence_nodes:
        payload = node.selector_payload or {}
        stage = payload.get("stage")
        if not isinstance(stage, str):
            continue
        if node.page_no is None or not (node.block_ids or []):
            continue
        stage_map.setdefault(stage, []).append(
            LessonPlanEvidenceAnchor(
                page_no=node.page_no,
                block_ids=node.block_ids or [],
                paragraph_ref=node.paragraph_ref,
                quote=_truncate(node.summary or node.title),
                selector_payload={
                    "selector_type": "block",
                    "block_id": (node.block_ids or [""])[0],
                    "node_type": "evidence",
                    "stage": stage,
                },
            )
        )
    return stage_map


def _match_stage(
    section: ParsedDocumentSection,
    block: ParsedDocumentBlock,
) -> str | None:
    haystack = f"{_normalize_text(section.title)} {_normalize_text(block.text)}".lower()
    for stage, _, keywords in _STAGES:
        if any(keyword in haystack for keyword in keywords):
            return stage
    return None


def _fallback_anchor(
    block: ParsedDocumentBlock, stage: str
) -> LessonPlanEvidenceAnchor:
    return LessonPlanEvidenceAnchor(
        page_no=block.page_no,
        block_ids=[block.block_id],
        paragraph_ref=str(block.paragraph_no)
        if block.paragraph_no is not None
        else None,
        quote=_truncate(block.text or "证据摘录缺失。"),
        selector_payload={
            "selector_type": "block",
            "block_id": block.block_id,
            "node_type": "lesson_plan_evidence",
            "stage": stage,
        },
    )


def build_stage_lesson_plan(
    payload: ParsedDocumentPayload,
    story_evidence: dict[str, list[LessonPlanEvidenceAnchor]],
) -> AssetLessonPlanPayload:
    sections_by_id = {section.section_id: section for section in payload.sections}
    candidate_blocks = sorted(payload.blocks, key=lambda item: item.order)
    stage_fallbacks: dict[str, list[LessonPlanEvidenceAnchor]] = {
        stage: [] for stage, _, _ in _STAGES
    }

    for block in candidate_blocks:
        section = sections_by_id.get(block.section_id)
        if section is None:
            continue
        stage = _match_stage(section, block)
        if stage is None:
            continue
        stage_fallbacks[stage].append(_fallback_anchor(block, stage))

    any_fallback_anchor = None
    for block in candidate_blocks:
        if block.page_no >= 1:
            any_fallback_anchor = _fallback_anchor(block, "problem")
            break

    stages: list[LessonPlanStage] = []
    for stage, title, _ in _STAGES:
        anchors = story_evidence.get(stage) or stage_fallbacks.get(stage) or []
        if not anchors and any_fallback_anchor is not None:
            anchors = [
                LessonPlanEvidenceAnchor(
                    page_no=any_fallback_anchor.page_no,
                    block_ids=any_fallback_anchor.block_ids,
                    paragraph_ref=any_fallback_anchor.paragraph_ref,
                    quote=any_fallback_anchor.quote,
                    selector_payload={
                        **any_fallback_anchor.selector_payload,
                        "stage": stage,
                    },
                )
            ]

        stages.append(
            LessonPlanStage(
                stage=stage,
                title=title,
                goal=f"完成“{title}”阶段讲解，帮助学习者建立主线理解。",
                script=LESSON_PLAN_PLACEHOLDER_SCRIPT,
                evidence_anchors=anchors[:2],
                source_section_hints=[],
            )
        )

    return AssetLessonPlanPayload(
        asset_id=payload.asset_id,
        version=1,
        generated_at=datetime.now(timezone.utc).isoformat(),
        stages=stages,
    )


def build_lesson_plan_summary(
    lesson_plan: AssetLessonPlanPayload,
) -> list[LessonPlanStageSummary]:
    return [
        LessonPlanStageSummary(
            stage=stage.stage,
            title=stage.title,
            anchor_count=len(stage.evidence_anchors),
        )
        for stage in lesson_plan.stages
    ]


def _bootstrap_presentation(db: Session, asset_id: str) -> None:
    statement = insert(Presentation).values(
        id=str(uuid4()),
        asset_id=asset_id,
        version=0,
        status="pending",
        lesson_plan=None,
        slides_dsl=None,
        dsl_quality_report={},
        dsl_fix_logs=[],
        error_meta={},
        active_run_token=None,
    )
    statement = statement.on_conflict_do_nothing(index_elements=[Presentation.asset_id])
    db.execute(statement)


def enqueue_asset_lesson_plan_rebuild(
    db: Session,
    asset_id: str,
) -> tuple[Asset, bool, str]:
    asset = _require_asset(db, asset_id)
    stale_timeout_sec = max(settings.slides_processing_stale_timeout_sec, 1)
    now = datetime.now(timezone.utc)
    reclaim_stale_processing = (
        asset.slides_status == "processing"
        and is_slides_processing_stale(
            updated_at=asset.updated_at,
            now=now,
            stale_after_seconds=stale_timeout_sec,
        )
    )
    allowed_slides_status = {"not_generated", "ready", "failed"}
    if reclaim_stale_processing:
        allowed_slides_status.add("processing")
    updated_rows = db.execute(
        update(Asset)
        .where(
            Asset.id == asset_id,
            Asset.parse_status == "ready",
            Asset.slides_status.in_(allowed_slides_status),
        )
        .values(slides_status="processing")
    ).rowcount

    if updated_rows == 0:
        db.refresh(asset)
        allowed, reason = can_enqueue_lesson_plan_rebuild(
            parse_status=asset.parse_status,
            slides_status=asset.slides_status,
        )
        if not allowed and reason == "parse_not_ready":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="当前资产解析尚未完成，暂时无法生成 lesson_plan。",
            )
        return asset, False, "当前资产 lesson_plan 正在生成中（已忽略重复触发）。"

    _bootstrap_presentation(db, asset_id)
    db.execute(
        update(Presentation)
        .where(Presentation.asset_id == asset_id)
        .values(status="processing")
    )
    db.commit()
    db.refresh(asset)
    if reclaim_stale_processing:
        return (
            asset,
            True,
            "检测到陈旧 processing 状态，已重新加入 lesson_plan 生成队列。",
        )
    return asset, True, "已加入 lesson_plan 生成队列。"


def _presentation_to_snapshot(
    presentation: Presentation,
) -> PresentationSnapshot:
    payload = None
    if presentation.lesson_plan:
        payload = AssetLessonPlanPayload.model_validate(presentation.lesson_plan)
    return PresentationSnapshot(
        id=presentation.id,
        asset_id=presentation.asset_id,
        version=presentation.version,
        status=presentation.status,
        lesson_plan=payload,
        error_meta=presentation.error_meta or {},
        created_at=presentation.created_at,
        updated_at=presentation.updated_at,
    )


def get_asset_lesson_plan(db: Session, asset_id: str) -> AssetLessonPlanResponse:
    asset = _require_asset(db, asset_id)
    presentation = db.scalars(
        select(Presentation).where(Presentation.asset_id == asset_id)
    ).first()
    if presentation is None:
        return AssetLessonPlanResponse(
            asset_id=asset.id,
            slides_status=asset.slides_status,
            presentation=None,
            summary=[],
        )

    snapshot = _presentation_to_snapshot(presentation)
    summary = (
        build_lesson_plan_summary(snapshot.lesson_plan)
        if snapshot.lesson_plan is not None
        else []
    )
    return AssetLessonPlanResponse(
        asset_id=asset.id,
        slides_status=asset.slides_status,
        presentation=snapshot,
        summary=summary,
    )


def run_asset_lesson_plan_pipeline(
    db: Session,
    asset_id: str,
    retry_meta: dict[str, str | int | bool | None] | None = None,
) -> dict[str, str | int]:
    asset = _require_asset(db, asset_id)
    if asset.parse_status != "ready":
        raise RuntimeError("当前资产解析尚未完成，无法生成 lesson_plan。")

    _bootstrap_presentation(db, asset_id)
    run_token = uuid4().hex
    presentation = db.scalars(
        select(Presentation).where(Presentation.asset_id == asset_id).with_for_update()
    ).one()
    presentation.status = "processing"
    presentation.active_run_token = run_token
    db.commit()

    try:
        payload = _load_parsed_payload(db, asset_id)
        story_evidence = _load_story_evidence(db, asset_id)
        lesson_plan = build_stage_lesson_plan(payload, story_evidence)

        presentation = db.scalars(
            select(Presentation)
            .where(Presentation.asset_id == asset_id)
            .with_for_update()
        ).one()
        if presentation.active_run_token != run_token:
            return {
                "asset_id": asset_id,
                "status": "stale_run_ignored",
            }

        presentation.lesson_plan = lesson_plan.model_dump(mode="json")
        presentation.version = int(presentation.version) + 1
        presentation.status = "ready"
        presentation.error_meta = {}
        presentation.active_run_token = None
        asset = _require_asset(db, asset_id)
        asset.slides_status = "processing"
        db.commit()
        return {
            "asset_id": asset_id,
            "status": "ready",
            "version": presentation.version,
        }
    except Exception as exc:
        logger.exception("lesson_plan 生成失败: asset_id=%s", asset_id, exc_info=exc)
        presentation = db.scalars(
            select(Presentation)
            .where(Presentation.asset_id == asset_id)
            .with_for_update()
        ).one()
        if presentation.active_run_token == run_token:
            presentation.status = "failed"
            presentation.error_meta = {
                "error_message": str(exc)[:500],
                "retry": retry_meta or {},
                "failed_at": datetime.now(timezone.utc).isoformat(),
            }
            presentation.active_run_token = None
            asset = _require_asset(db, asset_id)
            asset.slides_status = "failed"
            db.commit()
        return {
            "asset_id": asset_id,
            "status": "failed",
        }


def to_lesson_plan_rebuild_response(
    asset: Asset,
    message: str,
) -> AssetLessonPlanRebuildResponse:
    return AssetLessonPlanRebuildResponse(
        asset_id=asset.id,
        slides_status=asset.slides_status,
        message=message,
    )
