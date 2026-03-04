from __future__ import annotations

import io
import json
import logging
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.asset import Asset
from app.models.asset_file import AssetFile
from app.models.document_parse import DocumentParse
from app.schemas.document_parse import AssetParseStatusResponse, DocumentParseSummary, ParseProgress, ParseTaskSnapshot
from app.services.mineru_service import (
    MinerUConfigurationError,
    MinerURequestError,
    download_parse_zip,
    poll_parse_task,
    submit_parse_task,
)
from app.services.parse_normalizer import ParseBundle, normalize_parsed_json
from app.services.parse_storage_service import StoredArtifact, persist_parse_artifacts

logger = logging.getLogger(__name__)


def _get_original_pdf_file(db: Session, asset_id: str) -> AssetFile | None:
    statement = (
        select(AssetFile)
        .where(AssetFile.asset_id == asset_id, AssetFile.file_type == "original_pdf")
        .order_by(AssetFile.created_at.desc())
    )
    return db.scalars(statement).first()


def _get_latest_parse(db: Session, asset_id: str) -> DocumentParse | None:
    statement = (
        select(DocumentParse)
        .where(DocumentParse.asset_id == asset_id)
        .order_by(DocumentParse.created_at.desc())
    )
    return db.scalars(statement).first()


def _upsert_asset_file(
    db: Session,
    asset_id: str,
    file_type: str,
    artifact: StoredArtifact,
) -> AssetFile:
    statement = (
        select(AssetFile)
        .where(AssetFile.asset_id == asset_id, AssetFile.file_type == file_type)
        .order_by(AssetFile.created_at.desc())
    )
    asset_file = db.scalars(statement).first()
    if asset_file is None:
        asset_file = AssetFile(
            asset_id=asset_id,
            file_type=file_type,
            storage_key=artifact.storage_key,
            public_url=artifact.public_url,
            mime_type=artifact.mime_type,
            size=artifact.size,
        )
        db.add(asset_file)
        return asset_file

    asset_file.storage_key = artifact.storage_key
    asset_file.public_url = artifact.public_url
    asset_file.mime_type = artifact.mime_type
    asset_file.size = artifact.size
    return asset_file


def _read_json(path: Path) -> dict[str, Any] | list[Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _find_first(base_dir: Path, *patterns: str) -> Path | None:
    for pattern in patterns:
        matches = sorted(base_dir.rglob(pattern))
        if matches:
            return matches[0]
    return None


def _load_parse_bundle(extracted_dir: Path) -> tuple[ParseBundle, dict[str, str]]:
    middle_json_path = _find_first(extracted_dir, "middle.json", "*middle.json")
    content_list_path = _find_first(extracted_dir, "content_list.json", "*content_list.json")
    markdown_path = _find_first(extracted_dir, "*.md")

    if content_list_path is None:
        raise MinerURequestError("MinerU 结果中缺少 content_list.json。")

    content_list_data = _read_json(content_list_path)
    if not isinstance(content_list_data, list):
        raise MinerURequestError("content_list.json 不是预期的数组结构。")

    middle_json_data: dict[str, Any] = {}
    if middle_json_path is not None:
        loaded_middle_json = _read_json(middle_json_path)
        if isinstance(loaded_middle_json, dict):
            middle_json_data = loaded_middle_json

    markdown = _read_text(markdown_path) if markdown_path is not None else None
    discovered_files = {
        "content_list_path": content_list_path.relative_to(extracted_dir).as_posix(),
        "middle_json_path": middle_json_path.relative_to(extracted_dir).as_posix() if middle_json_path else "",
        "markdown_path": markdown_path.relative_to(extracted_dir).as_posix() if markdown_path else "",
    }
    return ParseBundle(content_list=content_list_data, middle_json=middle_json_data, markdown=markdown), discovered_files


def _build_task_snapshot(document_parse: DocumentParse) -> ParseTaskSnapshot:
    task_meta = document_parse.parser_meta.get("task", {})
    progress_meta = task_meta.get("progress") or {}
    progress = ParseProgress(
        extracted_pages=progress_meta.get("extracted_pages"),
        total_pages=progress_meta.get("total_pages"),
        start_time=progress_meta.get("start_time"),
    )
    return ParseTaskSnapshot(
        task_id=task_meta.get("task_id"),
        data_id=task_meta.get("data_id"),
        state=task_meta.get("state"),
        trace_id=task_meta.get("trace_id"),
        full_zip_url=task_meta.get("full_zip_url"),
        err_msg=task_meta.get("err_msg"),
        progress=progress,
    )


def to_document_parse_summary(document_parse: DocumentParse) -> DocumentParseSummary:
    """将解析 ORM 记录转换为接口响应。"""
    return DocumentParseSummary(
        id=document_parse.id,
        asset_id=document_parse.asset_id,
        provider=document_parse.provider,
        parse_version=document_parse.parse_version,
        status=document_parse.status,
        markdown_storage_key=document_parse.markdown_storage_key,
        json_storage_key=document_parse.json_storage_key,
        raw_response_storage_key=document_parse.raw_response_storage_key,
        task=_build_task_snapshot(document_parse),
        created_at=document_parse.created_at,
        updated_at=document_parse.updated_at,
    )


def get_asset_parse_status(db: Session, asset_id: str) -> AssetParseStatusResponse | None:
    """返回资产的最新解析状态。"""
    asset = db.get(Asset, asset_id)
    if asset is None:
        return None

    latest_parse = _get_latest_parse(db, asset_id)
    return AssetParseStatusResponse(
        asset_id=asset.id,
        asset_status=asset.status,
        parse_status=asset.parse_status,
        error_message=asset.parse_error_message,
        latest_parse=to_document_parse_summary(latest_parse) if latest_parse else None,
    )


def enqueue_asset_parse_retry(db: Session, asset_id: str) -> tuple[Asset, bool]:
    """将资产重新推进到等待解析状态。"""
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到对应的学习资产。")

    original_pdf = _get_original_pdf_file(db, asset_id)
    if original_pdf is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前资产缺少原始 PDF，无法重试解析。")

    if asset.parse_status in {"queued", "processing"}:
        return asset, False

    asset.status = "queued"
    asset.parse_status = "queued"
    asset.parse_error_message = None
    db.commit()
    db.refresh(asset)
    return asset, True


def _task_meta_from_result(result: Any) -> dict[str, Any]:
    return {
        "task_id": result.task_id,
        "data_id": result.data_id,
        "state": result.state,
        "trace_id": result.trace_id,
        "full_zip_url": result.full_zip_url,
        "err_msg": result.err_msg,
        "progress": result.progress,
    }


def _fail_parse(
    db: Session,
    asset: Asset,
    document_parse: DocumentParse,
    message: str,
    exception: Exception | None = None,
) -> None:
    asset.status = "failed"
    asset.parse_status = "failed"
    asset.parse_error_message = message
    document_parse.status = "failed"
    document_parse.parser_meta = {
        **document_parse.parser_meta,
        "failure_reason": message,
    }
    db.commit()
    if exception is not None:
        logger.exception("资产解析失败: asset_id=%s", asset.id, exc_info=exception)
    else:
        logger.error("资产解析失败: asset_id=%s, reason=%s", asset.id, message)


def run_parse_pipeline(db: Session, asset_id: str) -> DocumentParse:
    """执行单个资产的完整解析链路。"""
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise ValueError(f"未找到学习资产: {asset_id}")

    original_pdf = _get_original_pdf_file(db, asset_id)
    if original_pdf is None:
        raise ValueError(f"资产缺少原始 PDF 文件: {asset_id}")

    latest_parse = _get_latest_parse(db, asset_id)
    if latest_parse is not None and latest_parse.status == "running" and asset.parse_status == "processing":
        logger.info("跳过重复解析任务: asset_id=%s parse_id=%s", asset_id, latest_parse.id)
        return latest_parse

    asset.status = "processing"
    asset.parse_status = "processing"
    asset.parse_error_message = None

    document_parse = DocumentParse(
        asset_id=asset.id,
        provider="mineru",
        parse_version=settings.mineru_model_version,
        status="running",
        parser_meta={
            "source_pdf_url": original_pdf.public_url,
            "task": {},
        },
    )
    db.add(document_parse)
    db.commit()
    db.refresh(document_parse)
    db.refresh(asset)

    try:
        submit_result = submit_parse_task(original_pdf.public_url)
        document_parse.parser_meta = {
            **document_parse.parser_meta,
            "task": _task_meta_from_result(submit_result),
            "request": {
                "source_pdf_url": original_pdf.public_url,
                "backend": settings.mineru_model_version,
            },
        }
        db.commit()

        final_result = poll_parse_task(submit_result.task_id)
        document_parse.parser_meta = {
            **document_parse.parser_meta,
            "task": _task_meta_from_result(final_result),
        }
        if final_result.state in {"failed", "error"}:
            failure_message = final_result.err_msg or "MinerU 返回失败状态。"
            _fail_parse(db, asset, document_parse, failure_message)
            return document_parse

        if not final_result.full_zip_url:
            _fail_parse(db, asset, document_parse, "MinerU 任务成功但未返回结果包地址。")
            return document_parse

        raw_zip_bytes = download_parse_zip(final_result.full_zip_url)
        with tempfile.TemporaryDirectory() as temp_dir_name:
            extracted_dir = Path(temp_dir_name)
            with zipfile.ZipFile(io.BytesIO(raw_zip_bytes)) as archive:
                archive.extractall(extracted_dir)

            parse_bundle, discovered_files = _load_parse_bundle(extracted_dir)
            document_parse.parser_meta = {
                **document_parse.parser_meta,
                "task": _task_meta_from_result(final_result),
                "discovered_files": discovered_files,
            }
            parsed_json = normalize_parsed_json(parse_bundle, asset, document_parse)
            stored_artifacts = persist_parse_artifacts(
                user_id=asset.user_id,
                asset_id=asset.id,
                parse_id=document_parse.id,
                raw_zip_bytes=raw_zip_bytes,
                extracted_dir=extracted_dir,
                parsed_json=parsed_json,
                markdown=parse_bundle.markdown,
            )

        _upsert_asset_file(db, asset.id, "parsed_json", stored_artifacts.parsed_json)
        _upsert_asset_file(db, asset.id, "parse_raw_zip", stored_artifacts.raw_zip)
        if stored_artifacts.markdown is not None:
            _upsert_asset_file(db, asset.id, "parsed_markdown", stored_artifacts.markdown)

        document_parse.json_storage_key = stored_artifacts.parsed_json.storage_key
        document_parse.raw_response_storage_key = stored_artifacts.raw_zip.storage_key
        if stored_artifacts.markdown is not None:
            document_parse.markdown_storage_key = stored_artifacts.markdown.storage_key
        document_parse.status = "succeeded"
        document_parse.parser_meta = {
            **document_parse.parser_meta,
            "storage": {
                "parsed_json": stored_artifacts.parsed_json.storage_key,
                "raw_zip": stored_artifacts.raw_zip.storage_key,
                "markdown": stored_artifacts.markdown.storage_key if stored_artifacts.markdown else None,
                "archived_file_count": len(stored_artifacts.archived_files),
            },
        }

        asset.status = "ready"
        asset.parse_status = "ready"
        asset.parse_error_message = None
        db.commit()
        db.refresh(document_parse)
        return document_parse
    except (MinerUConfigurationError, MinerURequestError) as exc:
        _fail_parse(db, asset, document_parse, str(exc), exc)
        return document_parse
    except zipfile.BadZipFile as exc:
        _fail_parse(db, asset, document_parse, "MinerU 返回的结果包不是合法 ZIP。", exc)
        return document_parse
    except Exception as exc:  # pragma: no cover - 兜底未知异常
        _fail_parse(db, asset, document_parse, "解析链路发生未预期错误。", exc)
        return document_parse
