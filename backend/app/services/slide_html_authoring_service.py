from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

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
    if html_writer is _default_html_writer:
        try:
            return generate_slide_html_page(scene_spec, deck_style_guide=deck_style_guide)
        except Exception:
            rendered = html_writer(scene_spec)
    else:
        rendered = _call_html_writer(html_writer, scene_spec, deck_style_guide)
    render_meta = rendered.get("render_meta") if isinstance(rendered.get("render_meta"), dict) else {}
    return {
        "page_id": scene_spec["page_id"],
        "html": rendered["html"],
        "css": rendered["css"],
        "asset_refs": scene_spec.get("asset_bindings", []),
        "render_meta": {
            "layout_strategy": scene_spec.get("layout_strategy", ""),
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
