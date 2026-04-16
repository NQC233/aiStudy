from __future__ import annotations


def build_runtime_bundle(rendered_pages: list[dict[str, object]]) -> dict[str, object]:
    return {
        "page_count": len(rendered_pages),
        "pages": rendered_pages,
    }
