from __future__ import annotations

from dataclasses import dataclass, field
import re

from app.core.config import settings
from app.schemas.reader import ParsedDocumentBlock, ParsedDocumentPayload, ParsedDocumentSection

SUPPORTED_BLOCK_TYPES = {"heading", "paragraph", "list", "table", "equation"}


@dataclass
class ChunkBuildResult:
    chunk_index: int
    section_path: list[str]
    page_start: int | None
    page_end: int | None
    paragraph_start: int | None
    paragraph_end: int | None
    block_ids: list[str]
    text_content: str
    token_count: int


@dataclass
class _ChunkAccumulator:
    section_path: list[str]
    text_parts: list[str] = field(default_factory=list)
    block_ids: list[str] = field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None
    paragraph_start: int | None = None
    paragraph_end: int | None = None

    def append(self, block: ParsedDocumentBlock, normalized_text: str) -> None:
        self.text_parts.append(normalized_text)
        self.block_ids.append(block.block_id)
        self.page_start = block.page_no if self.page_start is None else min(self.page_start, block.page_no)
        self.page_end = block.page_no if self.page_end is None else max(self.page_end, block.page_no)
        if block.paragraph_no is not None:
            self.paragraph_start = (
                block.paragraph_no if self.paragraph_start is None else min(self.paragraph_start, block.paragraph_no)
            )
            self.paragraph_end = (
                block.paragraph_no if self.paragraph_end is None else max(self.paragraph_end, block.paragraph_no)
            )

    @property
    def text_content(self) -> str:
        return "\n".join(self.text_parts).strip()

    @property
    def text_length(self) -> int:
        return len(self.text_content)


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"[ \t]+", " ", text).strip()


def _estimate_token_count(text: str) -> int:
    tokens = re.findall(r"\S+", text)
    if tokens:
        return len(tokens)
    return len(text)


def _is_author_list_text(normalized_text: str) -> bool:
    lowered = normalized_text.lower()
    author_markers = ("google brain", "google research", "university of toronto", "@google.com")
    marker_hits = sum(1 for marker in author_markers if marker in lowered)
    return marker_hits >= 1 and (
        normalized_text.count("\n") >= 2
        or len(normalized_text.split()) <= 10
    )


def _is_permission_boilerplate(normalized_text: str) -> bool:
    lowered = normalized_text.lower()
    blocked_substrings = (
        "grants permission to reproduce the tables and figures",
        "provided proper attribution is provided",
        "permission to reproduce",
    )
    return any(token in lowered for token in blocked_substrings)


def _is_reference_noise(normalized_text: str, section_path: list[str]) -> bool:
    lowered = normalized_text.lower()
    if any(section.strip().lower() == "references" for section in section_path):
        return True
    return lowered.startswith("[") and "et al." in lowered


def _is_heading_only_noise(block: ParsedDocumentBlock, normalized_text: str) -> bool:
    if block.type != "heading":
        return False
    lowered = normalized_text.lower()
    if re.fullmatch(r"\d+(?:\.\d+)*\s+[a-z][a-z\s-]{1,40}", lowered):
        return True
    return len(normalized_text) <= 24


def _is_broken_ocr_noise(normalized_text: str) -> bool:
    if len(normalized_text) < 24:
        return False
    lowered = normalized_text.lower()
    suspicious_tokens = ("visualizations", "input-input", "layer", "attention")
    if sum(1 for token in suspicious_tokens if token in lowered) >= 2 and bool(re.search(r"[a-z][A-Z]", normalized_text)):
        return True
    return bool(re.search(r"[a-z][A-Z]", normalized_text)) and " " not in normalized_text[:24]


def _should_index_block(
    block: ParsedDocumentBlock,
    normalized_text: str,
    section_path: list[str],
) -> bool:
    lowered = normalized_text.lower()
    if lowered == "attention is all you need":
        return False
    if block.page_no == 1 and section_path[:2] == ["Attention Is All You Need", "Attention Is All You Need"]:
        if _is_author_list_text(normalized_text):
            return False
    if _is_author_list_text(normalized_text):
        return False
    if _is_permission_boilerplate(normalized_text):
        return False
    if _is_reference_noise(normalized_text, section_path):
        return False
    if _is_heading_only_noise(block, normalized_text):
        return False
    if _is_broken_ocr_noise(normalized_text):
        return False
    return True


def _build_section_map(sections: list[ParsedDocumentSection]) -> dict[str, ParsedDocumentSection]:
    return {section.section_id: section for section in sections}


def _resolve_section_path(
    section_id: str,
    section_map: dict[str, ParsedDocumentSection],
) -> list[str]:
    path: list[str] = []
    visited: set[str] = set()
    current = section_map.get(section_id)
    while current is not None and current.section_id not in visited:
        visited.add(current.section_id)
        if current.title:
            path.append(current.title.strip())
        if current.parent_id is None:
            break
        current = section_map.get(current.parent_id)
    path.reverse()
    return path


def _ordered_blocks(payload: ParsedDocumentPayload) -> list[ParsedDocumentBlock]:
    block_by_id = {block.block_id: block for block in payload.blocks}
    ordered: list[ParsedDocumentBlock] = []
    consumed: set[str] = set()

    for block_id in payload.reading_order:
        block = block_by_id.get(block_id)
        if block is None:
            continue
        ordered.append(block)
        consumed.add(block.block_id)

    for block in sorted(payload.blocks, key=lambda item: item.order):
        if block.block_id in consumed:
            continue
        ordered.append(block)
    return ordered


def _block_by_id(payload: ParsedDocumentPayload) -> dict[str, ParsedDocumentBlock]:
    return {block.block_id: block for block in payload.blocks}


def _build_asset_context_text(
    asset: dict[str, object],
    block_lookup: dict[str, ParsedDocumentBlock],
) -> str:
    caption_items = asset.get("caption")
    caption_text = ""
    if isinstance(caption_items, list):
        caption_text = " ".join(str(item).strip() for item in caption_items if str(item).strip())

    context_text = ""
    block_id = str(asset.get("block_id") or "")
    if block_id:
        parent_block = block_lookup.get(block_id)
        if parent_block is not None and parent_block.text:
            context_text = _normalize_text(parent_block.text)

    parts = [part for part in [caption_text, context_text] if part]
    return "\n".join(parts).strip()


def _build_asset_chunks(
    payload: ParsedDocumentPayload,
    section_map: dict[str, ParsedDocumentSection],
) -> list[ChunkBuildResult]:
    block_lookup = _block_by_id(payload)
    asset_chunks: list[ChunkBuildResult] = []

    for resource_group in (payload.assets.images, payload.assets.tables):
        for asset in resource_group:
            resource_id = str(asset.get("resource_id") or "").strip()
            if not resource_id:
                continue

            text_content = _build_asset_context_text(asset, block_lookup)
            if not text_content:
                continue

            block_id = str(asset.get("block_id") or "")
            parent_block = block_lookup.get(block_id) if block_id else None
            section_path = (
                _resolve_section_path(parent_block.section_id, section_map)
                if parent_block is not None
                else []
            )
            page_no = asset.get("page_no") or (parent_block.page_no if parent_block is not None else None)
            paragraph_no = parent_block.paragraph_no if parent_block is not None else None
            block_ids = [f"asset:{resource_id}"]
            if block_id:
                block_ids.append(block_id)

            asset_chunks.append(
                ChunkBuildResult(
                    chunk_index=0,
                    section_path=section_path,
                    page_start=page_no,
                    page_end=page_no,
                    paragraph_start=paragraph_no,
                    paragraph_end=paragraph_no,
                    block_ids=block_ids,
                    text_content=text_content,
                    token_count=_estimate_token_count(text_content),
                )
            )

    return asset_chunks


def build_chunks_from_parsed_payload(payload: ParsedDocumentPayload) -> list[ChunkBuildResult]:
    """基于 parsed_json 构建可检索 chunk。"""
    section_map = _build_section_map(payload.sections)
    ordered_blocks = _ordered_blocks(payload)
    target_chars = max(settings.kb_chunk_target_chars, 200)
    max_chars = max(settings.kb_chunk_max_chars, target_chars)

    chunks: list[ChunkBuildResult] = []
    current: _ChunkAccumulator | None = None

    def flush_current() -> None:
        nonlocal current
        if current is None:
            return
        text_content = current.text_content
        if not text_content:
            current = None
            return
        chunks.append(
            ChunkBuildResult(
                chunk_index=len(chunks) + 1,
                section_path=current.section_path,
                page_start=current.page_start,
                page_end=current.page_end,
                paragraph_start=current.paragraph_start,
                paragraph_end=current.paragraph_end,
                block_ids=current.block_ids.copy(),
                text_content=text_content,
                token_count=_estimate_token_count(text_content),
            )
        )
        current = None

    for block in ordered_blocks:
        if block.type not in SUPPORTED_BLOCK_TYPES:
            continue
        normalized_text = _normalize_text(block.text)
        if not normalized_text:
            continue

        section_path = _resolve_section_path(block.section_id, section_map)
        if not _should_index_block(block, normalized_text, section_path):
            continue
        if current is None:
            current = _ChunkAccumulator(section_path=section_path)
        else:
            projected_length = current.text_length + len(normalized_text) + 1
            should_split_by_section = bool(current.block_ids) and section_path != current.section_path
            should_split_by_size = bool(current.block_ids) and projected_length > max_chars
            should_split_by_heading = block.type == "heading" and current.text_length >= max(200, target_chars // 3)
            if should_split_by_section or should_split_by_size or should_split_by_heading:
                flush_current()
                current = _ChunkAccumulator(section_path=section_path)

        current.append(block, normalized_text)
        if current.text_length >= target_chars and block.type != "heading":
            flush_current()

    flush_current()

    for asset_chunk in _build_asset_chunks(payload, section_map):
        asset_chunk.chunk_index = len(chunks) + 1
        chunks.append(asset_chunk)

    return chunks
