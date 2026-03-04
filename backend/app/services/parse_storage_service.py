from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path

from app.services.oss_service import build_parse_artifact_key, upload_bytes


@dataclass
class StoredArtifact:
    """单个持久化产物的存储信息。"""

    storage_key: str
    public_url: str
    mime_type: str
    size: int


@dataclass
class StoredParseArtifacts:
    """一轮解析需要落盘的核心产物。"""

    raw_zip: StoredArtifact
    parsed_json: StoredArtifact
    markdown: StoredArtifact | None = None
    archived_files: dict[str, StoredArtifact] = field(default_factory=dict)


def _guess_mime_type(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path.name)
    return mime_type or "application/octet-stream"


def persist_parse_artifacts(
    user_id: str,
    asset_id: str,
    parse_id: str,
    raw_zip_bytes: bytes,
    extracted_dir: Path,
    parsed_json: dict,
    markdown: str | None,
) -> StoredParseArtifacts:
    """将原始结果、规范化结果和关键解压产物保存到 OSS。"""
    raw_zip_result = upload_bytes(
        storage_key=build_parse_artifact_key(user_id, asset_id, parse_id, "raw/result.zip"),
        content=raw_zip_bytes,
        content_type="application/zip",
    )
    parsed_json_bytes = json.dumps(parsed_json, ensure_ascii=False, indent=2).encode("utf-8")
    parsed_json_result = upload_bytes(
        storage_key=build_parse_artifact_key(user_id, asset_id, parse_id, "normalized/parsed.json"),
        content=parsed_json_bytes,
        content_type="application/json",
    )

    markdown_result: StoredArtifact | None = None
    if markdown is not None:
        markdown_bytes = markdown.encode("utf-8")
        uploaded_markdown = upload_bytes(
            storage_key=build_parse_artifact_key(user_id, asset_id, parse_id, "normalized/document.md"),
            content=markdown_bytes,
            content_type="text/markdown",
        )
        markdown_result = StoredArtifact(
            storage_key=uploaded_markdown.storage_key,
            public_url=uploaded_markdown.public_url,
            mime_type="text/markdown",
            size=len(markdown_bytes),
        )

    archived_files: dict[str, StoredArtifact] = {}
    for file_path in sorted(extracted_dir.rglob("*")):
        if not file_path.is_file():
            continue
        relative_path = file_path.relative_to(extracted_dir).as_posix()
        content = file_path.read_bytes()
        mime_type = _guess_mime_type(file_path)
        uploaded_file = upload_bytes(
            storage_key=build_parse_artifact_key(user_id, asset_id, parse_id, f"raw/extracted/{relative_path}"),
            content=content,
            content_type=mime_type,
        )
        archived_files[relative_path] = StoredArtifact(
            storage_key=uploaded_file.storage_key,
            public_url=uploaded_file.public_url,
            mime_type=mime_type,
            size=len(content),
        )

    return StoredParseArtifacts(
        raw_zip=StoredArtifact(
            storage_key=raw_zip_result.storage_key,
            public_url=raw_zip_result.public_url,
            mime_type="application/zip",
            size=len(raw_zip_bytes),
        ),
        parsed_json=StoredArtifact(
            storage_key=parsed_json_result.storage_key,
            public_url=parsed_json_result.public_url,
            mime_type="application/json",
            size=len(parsed_json_bytes),
        ),
        markdown=markdown_result,
        archived_files=archived_files,
    )
