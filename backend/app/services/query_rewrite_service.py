from __future__ import annotations

import re
from collections.abc import Callable

from app.services.llm_service import generate_retrieval_query_rewrite


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text))


def prepare_retrieval_query(
    *,
    query: str,
    rewrite_query: bool,
    rewrite_func: Callable[[str], str] | None = None,
) -> str:
    normalized = query.strip()
    if not normalized:
        return normalized
    if not rewrite_query:
        return normalized
    if not _contains_cjk(normalized):
        return normalized

    rewriter = rewrite_func or generate_retrieval_query_rewrite
    try:
        candidate = rewriter(normalized).strip()
    except Exception:
        return normalized

    return candidate or normalized
