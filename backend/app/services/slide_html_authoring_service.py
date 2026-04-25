from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
import re
from typing import Any

from app.services.llm_service import generate_slide_html_bundle
from app.services.llm_service import generate_slide_html_page


def _contains_fixed_canvas_contract(css: str, *, canvas_width: int, canvas_height: int) -> bool:
    normalized = re.sub(r"\s+", "", (css or "").lower())
    width_token = f"width:{int(canvas_width)}px"
    height_token = f"height:{int(canvas_height)}px"
    has_fixed_canvas = width_token in normalized and height_token in normalized
    has_hidden_overflow = "overflow:hidden" in normalized
    forbids_auto_growth = "min-height:100vh" not in normalized and "height:auto" not in normalized
    return has_fixed_canvas and has_hidden_overflow and forbids_auto_growth


def _contains_fixed_canvas_contract_in_html(html: str, *, canvas_width: int, canvas_height: int) -> bool:
    normalized = re.sub(r"\s+", "", (html or "").lower())
    width_token = f"width:{int(canvas_width)}px"
    height_token = f"height:{int(canvas_height)}px"
    has_fixed_canvas = normalized.count(width_token) >= 2 and normalized.count(height_token) >= 2
    has_hidden_overflow = normalized.count("overflow:hidden") >= 2
    forbids_auto_growth = "min-height:100vh" not in normalized and "height:auto" not in normalized
    return has_fixed_canvas and has_hidden_overflow and forbids_auto_growth


def validate_rendered_slide_page(
    *,
    page_number: int,
    html: str,
    css: str,
    canvas_width: int,
    canvas_height: int,
    timeout_sec: int,
) -> dict[str, Any]:
    del page_number, timeout_sec
    normalized_html = (html or "").lower()
    if not normalized_html.strip():
        return {
            "status": "failed",
            "blocking": True,
            "reason": "empty_html",
            "canvas_width": canvas_width,
            "canvas_height": canvas_height,
        }

    if not _contains_fixed_canvas_contract(
        css,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
    ) and not _contains_fixed_canvas_contract_in_html(
        html,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
    ):
        return {
            "status": "failed",
            "blocking": True,
            "reason": "canvas_contract_missing",
            "canvas_width": canvas_width,
            "canvas_height": canvas_height,
        }

    overflow_markers = (
        "height:2000px",
        "height: 2000px",
        "overflow:auto",
        "overflow: auto",
        "overflow:scroll",
        "overflow: scroll",
        "overflow-y:scroll",
        "overflow-y:auto",
    )
    if any(marker in normalized_html for marker in overflow_markers):
        return {
            "status": "failed",
            "blocking": True,
            "reason": "overflow_detected",
            "canvas_width": canvas_width,
            "canvas_height": canvas_height,
        }

    return {
        "status": "passed",
        "blocking": False,
        "reason": None,
        "canvas_width": canvas_width,
        "canvas_height": canvas_height,
    }


def build_slide_validation_result(
    *,
    enabled: bool,
    page_number: int,
    html: str,
    css: str,
    canvas_width: int,
    canvas_height: int,
    timeout_sec: int,
) -> dict[str, Any]:
    if not enabled:
        return {
            "status": "skipped",
            "blocking": False,
            "reason": "validation_disabled",
        }

    return validate_rendered_slide_page(
        page_number=page_number,
        html=html,
        css=css,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        timeout_sec=timeout_sec,
    )


def _default_html_writer(scene_spec: dict[str, object]) -> dict[str, str]:
    title = str(scene_spec.get("title", "Paper Overview")).strip() or "Paper Overview"
    summary_line = str(scene_spec.get("summary_line", "")).strip()
    content_html = f"<p>{summary_line}</p>" if summary_line else ""
    return {
        "html": f"<section class=\"slide-page\"><h1>{title}</h1>{content_html}</section>",
        "css": (
            ".slide-page{width:100%;height:100%;box-sizing:border-box;padding:72px 88px;"
            "background:#fff;color:#1f2937;font-family:Inter,system-ui,sans-serif;}"
            ".slide-page h1{margin:0 0 24px;font-size:42px;line-height:1.1;}"
            ".slide-page p{margin:0;font-size:24px;line-height:1.5;}"
        ),
    }


def apply_page_budget(scene_spec: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    budget = scene_spec.get("page_budget") if isinstance(scene_spec.get("page_budget"), dict) else {}
    content_budget = budget.get("content_budget") if isinstance(budget.get("content_budget"), dict) else {}
    bullet_max_items = int(content_budget.get("bullet_max_items", 4) or 4)
    max_blocks = int(budget.get("max_blocks", 3) or 3)

    trimmed_blocks: list[dict[str, object]] = []
    kept_blocks: list[dict[str, object]] = []
    blocks = scene_spec.get("content_blocks") if isinstance(scene_spec.get("content_blocks"), list) else []

    for raw_block in blocks[:max_blocks]:
        if not isinstance(raw_block, dict):
            kept_blocks.append(raw_block)
            continue
        if (
            raw_block.get("type") == "bullets"
            and isinstance(raw_block.get("items"), list)
            and len(raw_block["items"]) > bullet_max_items
        ):
            kept_blocks.append({**raw_block, "items": raw_block["items"][:bullet_max_items]})
            trimmed_blocks.append({**raw_block, "items": raw_block["items"][bullet_max_items:]})
            continue
        kept_blocks.append(raw_block)

    for raw_block in blocks[max_blocks:]:
        if isinstance(raw_block, dict):
            trimmed_blocks.append(raw_block)

    repair_hints = {
        "status": "trimmed" if trimmed_blocks else "clean",
        "trimmed_block_count": len(trimmed_blocks),
        "overflow_residue": trimmed_blocks,
        "suggested_next_action": "split" if trimmed_blocks else "none",
    }
    return {
        **scene_spec,
        "content_blocks": kept_blocks,
    }, repair_hints


def _call_html_writer(
    html_writer: Callable[..., dict[str, str]],
    scene_spec: dict[str, object],
    deck_style_guide: dict[str, object] | None,
) -> dict[str, str]:
    try:
        return html_writer(scene_spec, deck_style_guide=deck_style_guide)
    except TypeError:
        return html_writer(scene_spec)


def render_slide_page(
    scene_spec: dict[str, object],
    *,
    html_writer: Callable[..., dict[str, str]] = _default_html_writer,
    deck_style_guide: dict[str, object] | None = None,
) -> dict[str, object]:
    safe_scene_spec, repair_hints = apply_page_budget(scene_spec)
    if html_writer is _default_html_writer:
        try:
            rendered = generate_slide_html_page(safe_scene_spec, deck_style_guide=deck_style_guide)
        except Exception:
            rendered = html_writer(safe_scene_spec)
    else:
        rendered = _call_html_writer(html_writer, safe_scene_spec, deck_style_guide)
    render_meta = rendered.get("render_meta") if isinstance(rendered.get("render_meta"), dict) else {}
    return {
        "page_id": safe_scene_spec["page_id"],
        "html": rendered["html"],
        "css": rendered["css"],
        "asset_refs": safe_scene_spec.get("asset_bindings", []),
        "render_meta": {
            "layout_strategy": safe_scene_spec.get("layout_strategy", ""),
            "repair_hints": repair_hints,
            **render_meta,
        },
    }


def render_slide_pages(
    scene_specs: list[dict[str, object]],
    *,
    html_writer: Callable[..., dict[str, str]] = _default_html_writer,
    parallelism: int = 1,
    deck_style_guide: dict[str, object] | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    def render_one(scene_spec: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
        try:
            return (
                render_slide_page(
                    scene_spec,
                    html_writer=html_writer,
                    deck_style_guide=deck_style_guide,
                ),
                {
                    "page_id": scene_spec.get("page_id", "unknown"),
                    "status": "success",
                    "reason": "",
                },
            )
        except Exception as exc:
            return (
                render_slide_page(
                    scene_spec,
                    deck_style_guide=deck_style_guide,
                ),
                {
                    "page_id": scene_spec.get("page_id", "unknown"),
                    "status": "fallback",
                    "reason": str(exc),
                },
            )

    effective_parallelism = max(1, int(parallelism or 1))
    if effective_parallelism == 1 or len(scene_specs) <= 1:
        results = [render_one(scene_spec) for scene_spec in scene_specs]
    else:
        with ThreadPoolExecutor(max_workers=min(effective_parallelism, len(scene_specs))) as executor:
            futures = [executor.submit(render_one, scene_spec) for scene_spec in scene_specs]
            results = [future.result() for future in futures]

    rendered_pages = [item[0] for item in results]
    html_meta = [item[1] for item in results]
    return rendered_pages, html_meta


def _chunk_scene_specs(scene_specs: list[dict[str, object]], chunk_size: int) -> list[list[dict[str, object]]]:
    size = max(1, int(chunk_size or 1))
    return [scene_specs[index : index + size] for index in range(0, len(scene_specs), size)]


def _build_batch_fallback_bundle(
    scene_specs: list[dict[str, object]],
    *,
    deck_style_guide: dict[str, object] | None,
    deck_meta: dict[str, object] | None,
    page_html_writer: Callable[..., dict[str, str]],
) -> dict[str, object]:
    pages, html_meta = render_slide_pages(
        scene_specs,
        html_writer=page_html_writer,
        parallelism=1,
        deck_style_guide=deck_style_guide,
    )
    return {
        "deck_meta": deck_meta or {
            "theme_name": (deck_style_guide or {}).get("theme_name", "paper-academic"),
        },
        "pages": pages,
        "html_meta": html_meta,
    }



def _validate_batch_bundle_shape(bundle: dict[str, object]) -> None:
    pages = bundle.get("pages") if isinstance(bundle.get("pages"), list) else None
    if pages is None:
        raise ValueError("batch html writer returned invalid pages payload")
    for page in pages:
        if not isinstance(page, dict):
            raise ValueError("batch html writer returned invalid pages payload")
        if not isinstance(page.get("page_id"), str) or not isinstance(page.get("html"), str):
            raise ValueError("batch html writer returned invalid page payload")
        if not isinstance(page.get("css"), str) or not isinstance(page.get("render_meta"), dict):
            raise ValueError("batch html writer returned invalid page payload")



def _render_slide_pages_batch_chunk(
    scene_specs: list[dict[str, object]],
    *,
    deck_style_guide: dict[str, object] | None,
    deck_digest: dict[str, object] | None,
    batch_html_writer: Callable[..., dict[str, object]],
    deck_meta: dict[str, object] | None,
    page_html_writer: Callable[..., dict[str, str]],
) -> dict[str, object]:
    try:
        bundle = batch_html_writer(
            scene_specs,
            deck_style_guide=deck_style_guide,
            deck_digest=deck_digest or {},
            deck_meta=deck_meta,
            page_html_writer=page_html_writer,
        )
        _validate_batch_bundle_shape(bundle)
        return bundle
    except Exception:
        return _build_batch_fallback_bundle(
            scene_specs,
            deck_style_guide=deck_style_guide,
            deck_meta=deck_meta,
            page_html_writer=page_html_writer,
        )



def _default_batch_html_writer(
    scene_specs: list[dict[str, object]],
    *,
    deck_style_guide: dict[str, object] | None = None,
    deck_digest: dict[str, object] | None = None,
    deck_meta: dict[str, object] | None = None,
    page_html_writer: Callable[..., dict[str, str]] = _default_html_writer,
) -> dict[str, object]:
    del deck_digest
    try:
        bundle = generate_slide_html_bundle(
            scene_specs,
            deck_style_guide=deck_style_guide,
            deck_meta=deck_meta,
        )
        return {
            **bundle,
            "html_meta": [
                {
                    "status": "success",
                    "reason": "",
                    "mode": "batch",
                    "page_count": len(bundle.get("pages", [])),
                }
            ],
        }
    except Exception:
        return _build_batch_fallback_bundle(
            scene_specs,
            deck_style_guide=deck_style_guide,
            deck_meta=deck_meta,
            page_html_writer=page_html_writer,
        )


def render_slide_pages_batch(
    scene_specs: list[dict[str, object]],
    *,
    deck_style_guide: dict[str, object] | None = None,
    deck_digest: dict[str, object] | None = None,
    batch_html_writer: Callable[..., dict[str, object]] = _default_batch_html_writer,
    max_batch_pages: int = 12,
    chunk_size: int = 4,
    page_html_writer: Callable[..., dict[str, str]] = _default_html_writer,
) -> dict[str, object]:
    if len(scene_specs) <= max(1, int(max_batch_pages or 1)):
        return _render_slide_pages_batch_chunk(
            scene_specs,
            deck_style_guide=deck_style_guide,
            deck_digest=deck_digest,
            batch_html_writer=batch_html_writer,
            deck_meta=None,
            page_html_writer=page_html_writer,
        )

    bundle_pages: list[dict[str, object]] = []
    bundle_html_meta: list[dict[str, object]] = []
    shared_deck_meta: dict[str, object] = {}
    for chunk in _chunk_scene_specs(scene_specs, chunk_size):
        chunk_bundle = _render_slide_pages_batch_chunk(
            chunk,
            deck_style_guide=deck_style_guide,
            deck_digest=deck_digest,
            batch_html_writer=batch_html_writer,
            deck_meta=shared_deck_meta or None,
            page_html_writer=page_html_writer,
        )
        if not shared_deck_meta and isinstance(chunk_bundle.get("deck_meta"), dict):
            shared_deck_meta = chunk_bundle["deck_meta"]
        bundle_pages.extend(chunk_bundle.get("pages") if isinstance(chunk_bundle.get("pages"), list) else [])
        bundle_html_meta.extend(
            chunk_bundle.get("html_meta") if isinstance(chunk_bundle.get("html_meta"), list) else []
        )
    return {
        "deck_meta": shared_deck_meta,
        "pages": bundle_pages,
        "html_meta": bundle_html_meta,
    }
