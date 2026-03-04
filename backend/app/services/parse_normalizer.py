from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from app.models.asset import Asset
from app.models.document_parse import DocumentParse


@dataclass
class ParseBundle:
    """封装 MinerU 解压后的关键内容。"""

    content_list: list[dict[str, Any]]
    middle_json: dict[str, Any]
    markdown: str | None


def _ensure_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _as_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_page_idx(item: dict[str, Any]) -> int:
    for key in ("page_idx", "page_id", "page_no", "page_index"):
        value = _as_int(item.get(key))
        if value is not None:
            return max(value - 1, 0) if key == "page_no" and value > 0 else max(value, 0)
    return 0


def _extract_bbox(item: dict[str, Any]) -> list[float] | None:
    candidates = [
        item.get("bbox"),
        item.get("position"),
        item.get("poly"),
        item.get("box"),
    ]

    for candidate in candidates:
        if isinstance(candidate, list) and len(candidate) >= 4:
            bbox = [_as_float(value) for value in candidate[:4]]
            if all(value is not None for value in bbox):
                return [float(value) for value in bbox if value is not None]

    return None


def _extract_text(item: dict[str, Any]) -> str | None:
    for key in ("text", "content", "latex", "html", "table_body", "text_body", "code_body"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    texts: list[str] = []
    for key in ("caption", "img_caption", "table_caption", "footnote"):
        for value in _ensure_list(item.get(key)):
            if isinstance(value, str) and value.strip():
                texts.append(value.strip())

    if texts:
        return "\n".join(texts)
    return None


def _extract_resource_path(item: dict[str, Any]) -> str | None:
    for key in ("img_path", "image_path", "path", "file_path", "table_image_path"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_string_list(item: dict[str, Any], *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        for value in _ensure_list(item.get(key)):
            if isinstance(value, str) and value.strip():
                values.append(value.strip())
    return values


def _normalize_block_type(item: dict[str, Any]) -> str | None:
    raw_type = str(item.get("type") or item.get("category") or "paragraph").lower()
    mapping = {
        "text": "paragraph",
        "title": "heading",
        "image": "image",
        "figure": "image",
        "img": "image",
        "table": "table",
        "equation": "equation",
        "list": "list",
        "code": "code",
    }

    ignored_types = {"header", "footer", "page_number", "page_footnote", "aside_text"}
    if raw_type in ignored_types:
        return None

    normalized_type = mapping.get(raw_type, raw_type)
    text_level = _as_int(item.get("text_level"))
    if normalized_type == "paragraph" and text_level and text_level > 0:
        return "heading"
    return normalized_type


def _extract_pdf_pages(middle_json: dict[str, Any]) -> list[dict[str, Any]]:
    pdf_info = middle_json.get("pdf_info")
    if isinstance(pdf_info, list):
        return [page for page in pdf_info if isinstance(page, dict)]
    return []


def _page_size(page_info: dict[str, Any]) -> tuple[float | None, float | None]:
    page_size = page_info.get("page_size")
    if isinstance(page_size, list) and len(page_size) >= 2:
        return _as_float(page_size[0]), _as_float(page_size[1])

    page_bbox = page_info.get("page_bbox")
    if isinstance(page_bbox, list) and len(page_bbox) >= 4:
        left, top, right, bottom = page_bbox[:4]
        left_num = _as_float(left) or 0.0
        top_num = _as_float(top) or 0.0
        right_num = _as_float(right)
        bottom_num = _as_float(bottom)
        if right_num is not None and bottom_num is not None:
            return right_num - left_num, bottom_num - top_num

    return None, None


def _build_markdown_fallback(markdown: str) -> list[dict[str, Any]]:
    content_list: list[dict[str, Any]] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            heading_text = stripped.lstrip("#").strip()
            level = len(stripped) - len(stripped.lstrip("#"))
            content_list.append({"type": "text", "text": heading_text, "text_level": level, "page_idx": 0})
            continue
        content_list.append({"type": "text", "text": stripped, "text_level": 0, "page_idx": 0})
    return content_list


def normalize_parsed_json(bundle: ParseBundle, asset: Asset, document_parse: DocumentParse) -> dict[str, Any]:
    """将 MinerU 原始输出转换为平台内部 parsed_json。"""
    content_list = bundle.content_list or _build_markdown_fallback(bundle.markdown or "")
    pdf_pages = _extract_pdf_pages(bundle.middle_json)

    max_page_idx = 0
    for item in content_list:
        max_page_idx = max(max_page_idx, _extract_page_idx(item))
    page_count = max(len(pdf_pages), max_page_idx + 1, 1)

    pages: list[dict[str, Any]] = []
    page_blocks_map: dict[int, list[str]] = defaultdict(list)
    for page_idx in range(page_count):
        page_info = pdf_pages[page_idx] if page_idx < len(pdf_pages) else {}
        width, height = _page_size(page_info)
        pages.append(
            {
                "page_id": f"page-{page_idx + 1}",
                "page_no": page_idx + 1,
                "source_page_idx": page_idx,
                "width": width,
                "height": height,
                "blocks": [],
            }
        )

    sections: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    reading_order: list[str] = []
    images: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []

    section_stack: list[dict[str, Any]] = []
    root_section = {
        "section_id": "sec-000",
        "title": asset.title,
        "level": 0,
        "parent_id": None,
        "page_start": 1,
        "page_end": page_count,
        "block_ids": [],
    }
    sections.append(root_section)
    section_stack.append(root_section)

    paragraph_no = 0
    block_order = 0
    figure_count = 0
    table_count = 0
    equation_count = 0

    for index, item in enumerate(content_list):
        block_type = _normalize_block_type(item)
        if block_type is None:
            continue

        page_idx = _extract_page_idx(item)
        page_no = page_idx + 1
        block_order += 1
        paragraph_no += 1
        block_id = f"blk-{block_order:04d}"
        bbox = _extract_bbox(item)
        text_level = _as_int(item.get("text_level"))

        if block_type == "heading":
            level = text_level if text_level and text_level > 0 else 1
            while section_stack and section_stack[-1]["level"] >= level:
                section_stack.pop()
            parent_section = section_stack[-1] if section_stack else root_section
            section = {
                "section_id": f"sec-{len(sections):03d}",
                "title": _extract_text(item) or f"Section {len(sections)}",
                "level": level,
                "parent_id": parent_section["section_id"],
                "page_start": page_no,
                "page_end": page_no,
                "block_ids": [],
            }
            sections.append(section)
            section_stack.append(section)

        current_section = section_stack[-1] if section_stack else root_section
        current_section["page_end"] = max(int(current_section["page_end"]), page_no)

        block = {
            "block_id": block_id,
            "type": block_type,
            "page_no": page_no,
            "source_page_idx": page_idx,
            "order": block_order,
            "section_id": current_section["section_id"],
            "bbox": bbox,
            "text": _extract_text(item),
            "text_level": text_level,
            "paragraph_no": paragraph_no,
            "anchor": {
                "selector_type": "bbox",
                "selector_payload": {"bbox": bbox} if bbox else {},
            },
            "source_refs": {
                "content_list_index": index,
                "middle_json_path": item.get("middle_json_path") or f"pdf_info[{page_idx}]",
            },
            "resource_ref": None,
            "metadata": {},
        }

        if block_type == "image":
            figure_count += 1
            resource_id = f"img-{figure_count:03d}"
            resource = {
                "resource_id": resource_id,
                "type": "image",
                "page_no": page_no,
                "source_page_idx": page_idx,
                "path": _extract_resource_path(item),
                "caption": _extract_string_list(item, "img_caption", "caption"),
                "footnote": _extract_string_list(item, "footnote"),
                "bbox": bbox,
                "block_id": block_id,
            }
            images.append(resource)
            block["resource_ref"] = resource_id

        if block_type == "table":
            table_count += 1
            resource_id = f"tbl-{table_count:03d}"
            resource = {
                "resource_id": resource_id,
                "type": "table",
                "page_no": page_no,
                "source_page_idx": page_idx,
                "path": _extract_resource_path(item),
                "caption": _extract_string_list(item, "table_caption", "caption"),
                "footnote": _extract_string_list(item, "table_footnote", "footnote"),
                "html": item.get("table_body") or item.get("html"),
                "bbox": bbox,
                "block_id": block_id,
            }
            tables.append(resource)
            block["resource_ref"] = resource_id

        if block_type == "equation":
            equation_count += 1

        reading_order.append(block_id)
        blocks.append(block)
        page_blocks_map[page_idx].append(block_id)
        current_section["block_ids"].append(block_id)
        root_section["block_ids"].append(block_id)

    for page in pages:
        page["blocks"] = page_blocks_map[page["source_page_idx"]]

    toc = [
        {
            "section_id": section["section_id"],
            "title": section["title"],
            "level": section["level"],
            "page_start": section["page_start"],
        }
        for section in sections
        if section["level"] > 0
    ]

    return {
        "schema_version": "v1",
        "asset_id": asset.id,
        "parse_id": document_parse.id,
        "provider": {
            "name": document_parse.provider,
            "backend": document_parse.parse_version,
            "version": document_parse.parse_version,
            "source_zip_url": document_parse.parser_meta.get("full_zip_url"),
        },
        "document": {
            "title": asset.title,
            "authors": asset.authors,
            "abstract": asset.abstract,
            "language": asset.language,
            "page_count": page_count,
        },
        "pages": pages,
        "sections": sections,
        "blocks": blocks,
        "assets": {
            "images": images,
            "tables": tables,
        },
        "reading_order": reading_order,
        "toc": toc,
        "stats": {
            "text_block_count": sum(1 for block in blocks if block["type"] in {"heading", "paragraph", "list", "code"}),
            "figure_count": figure_count,
            "table_count": table_count,
            "equation_count": equation_count,
        },
    }
