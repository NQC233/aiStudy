from __future__ import annotations

from collections.abc import Callable

from app.services.llm_service import generate_slide_html_page


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


def render_slide_page(
    scene_spec: dict[str, object],
    *,
    html_writer: Callable[[dict[str, object]], dict[str, str]] = _default_html_writer,
) -> dict[str, object]:
    if html_writer is _default_html_writer:
        try:
            return generate_slide_html_page(scene_spec)
        except Exception:
            rendered = html_writer(scene_spec)
    else:
        rendered = html_writer(scene_spec)
    return {
        "page_id": scene_spec["page_id"],
        "html": rendered["html"],
        "css": rendered["css"],
        "asset_refs": scene_spec.get("asset_bindings", []),
        "render_meta": {"layout_strategy": scene_spec.get("layout_strategy", "")},
    }
