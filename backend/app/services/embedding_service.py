from __future__ import annotations

import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingConfigurationError(RuntimeError):
    """Embedding 配置错误。"""


class EmbeddingRequestError(RuntimeError):
    """Embedding 请求错误。"""


def _resolve_embedding_base_url() -> str:
    if settings.dashscope_embedding_base_url:
        return settings.dashscope_embedding_base_url
    if settings.dashscope_base_url:
        normalized = settings.dashscope_base_url.rstrip("/")
        if normalized.endswith("/chat/completions"):
            return normalized.replace("/chat/completions", "/embeddings")
        return f"{normalized}/embeddings"
    raise EmbeddingConfigurationError("未配置 DASHSCOPE_EMBEDDING_BASE_URL，且无法从 DASHSCOPE_BASE_URL 推导。")


def _build_payload(texts: list[str], text_type: str) -> dict[str, Any]:
    model_name = settings.dashscope_embedding_model_name.strip()
    if not model_name:
        raise EmbeddingConfigurationError("DASHSCOPE_EMBEDDING_MODEL_NAME 不能为空。")

    payload: dict[str, Any] = {
        "model": model_name,
        "input": texts if len(texts) > 1 else texts[0],
        "encoding_format": "float",
    }
    if settings.dashscope_embedding_dimension > 0:
        payload["dimensions"] = settings.dashscope_embedding_dimension
    if text_type in {"document", "query"}:
        payload["text_type"] = text_type
    return payload


def _post_embedding(payload: dict[str, Any]) -> dict[str, Any]:
    if not settings.dashscope_api_key:
        raise EmbeddingConfigurationError("未配置 DASHSCOPE_API_KEY，无法生成向量。")

    request = Request(
        url=_resolve_embedding_base_url(),
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.dashscope_api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8")
        except Exception:  # pragma: no cover - 兜底异常读取
            detail = str(exc)
        raise EmbeddingRequestError(f"Embedding 请求失败，状态码 {exc.code}，详情：{detail}") from exc
    except URLError as exc:
        raise EmbeddingRequestError("Embedding 请求失败，网络不可达。") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise EmbeddingRequestError("Embedding 响应不是合法 JSON。") from exc


def _extract_openai_embeddings(response_json: dict[str, Any]) -> list[list[float]] | None:
    data = response_json.get("data")
    if not isinstance(data, list):
        return None

    normalized: list[tuple[int, list[float]]] = []
    for fallback_index, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        embedding = item.get("embedding")
        if not isinstance(embedding, list):
            continue
        index = item.get("index")
        try:
            normalized_index = int(index) if index is not None else fallback_index
        except (TypeError, ValueError):
            normalized_index = fallback_index
        normalized.append((normalized_index, [float(value) for value in embedding]))

    if not normalized:
        return None
    normalized.sort(key=lambda item: item[0])
    return [item[1] for item in normalized]


def _extract_dashscope_embeddings(response_json: dict[str, Any]) -> list[list[float]] | None:
    output = response_json.get("output")
    if not isinstance(output, dict):
        return None
    embeddings = output.get("embeddings")
    if not isinstance(embeddings, list):
        return None

    normalized: list[tuple[int, list[float]]] = []
    for fallback_index, item in enumerate(embeddings):
        if not isinstance(item, dict):
            continue
        embedding = item.get("embedding")
        if not isinstance(embedding, list):
            continue
        index = item.get("text_index", item.get("index", fallback_index))
        try:
            normalized_index = int(index)
        except (TypeError, ValueError):
            normalized_index = fallback_index
        normalized.append((normalized_index, [float(value) for value in embedding]))

    if not normalized:
        return None
    normalized.sort(key=lambda item: item[0])
    return [item[1] for item in normalized]


def _validate_embeddings(embeddings: list[list[float]], expected_size: int) -> list[list[float]]:
    if len(embeddings) != expected_size:
        raise EmbeddingRequestError(f"Embedding 返回条数不匹配，期望 {expected_size}，实际 {len(embeddings)}。")

    configured_dimension = settings.dashscope_embedding_dimension
    if configured_dimension > 0:
        for index, embedding in enumerate(embeddings):
            if len(embedding) != configured_dimension:
                raise EmbeddingRequestError(
                    f"Embedding 维度不匹配，第 {index} 条期望 {configured_dimension}，实际 {len(embedding)}。"
                )
    return embeddings


def _embed_batch(texts: list[str], text_type: str) -> list[list[float]]:
    payload = _build_payload(texts=texts, text_type=text_type)
    response_json = _post_embedding(payload)
    embeddings = _extract_openai_embeddings(response_json) or _extract_dashscope_embeddings(response_json)
    if embeddings is None:
        raise EmbeddingRequestError("Embedding 响应中没有可用向量数据。")
    return _validate_embeddings(embeddings, expected_size=len(texts))


def embed_texts(texts: list[str], text_type: str = "document") -> list[list[float]]:
    """批量生成向量，默认按文档片段模式请求。"""
    cleaned_texts = [text.strip() for text in texts if text and text.strip()]
    if not cleaned_texts:
        return []

    batch_size = max(settings.dashscope_embedding_batch_size, 1)
    embeddings: list[list[float]] = []
    for start in range(0, len(cleaned_texts), batch_size):
        batch_texts = cleaned_texts[start : start + batch_size]
        logger.info("请求 embedding 批次: size=%s", len(batch_texts))
        embeddings.extend(_embed_batch(batch_texts, text_type=text_type))
    return embeddings
