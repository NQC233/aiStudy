from __future__ import annotations

import json
import socket
from collections.abc import Sequence
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings
from app.schemas.document_chunk import RetrievalSearchHit


class LLMConfigurationError(RuntimeError):
    """模型配置缺失或非法。"""


class LLMRequestError(RuntimeError):
    """模型请求失败。"""


def _ensure_chat_configuration() -> tuple[str, str, str]:
    if not settings.dashscope_api_key:
        raise LLMConfigurationError("未配置 DASHSCOPE_API_KEY，无法调用问答模型。")
    if not settings.dashscope_base_url:
        raise LLMConfigurationError("未配置 DASHSCOPE_BASE_URL，无法调用问答模型。")
    model_name = settings.dashscope_model_name.strip()
    if not model_name:
        raise LLMConfigurationError("DASHSCOPE_MODEL_NAME 不能为空。")
    return settings.dashscope_api_key, settings.dashscope_base_url, model_name


def _clip_text(text: str, limit: int = 1200) -> str:
    normalized = text.strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit].rstrip()}..."


def _build_context_lines(retrieval_hits: Sequence[RetrievalSearchHit]) -> str:
    lines: list[str] = []
    for index, hit in enumerate(retrieval_hits, start=1):
        section_label = " / ".join(hit.section_path) if hit.section_path else "未标注章节"
        page_label = "-"
        if hit.page_start is not None and hit.page_end is not None:
            page_label = f"{hit.page_start}-{hit.page_end}"
        elif hit.page_start is not None:
            page_label = str(hit.page_start)
        elif hit.page_end is not None:
            page_label = str(hit.page_end)
        lines.append(
            "\n".join(
                [
                    f"[{index}] chunk_id={hit.chunk_id} score={hit.score:.4f} pages={page_label}",
                    f"section={section_label}",
                    f"text={_clip_text(hit.text, limit=1200)}",
                ]
            )
        )
    return "\n\n".join(lines)


def _extract_message_content(response_json: dict[str, Any]) -> str | None:
    choices = response_json.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                text_parts: list[str] = []
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    text_value = item.get("text")
                    if isinstance(text_value, str):
                        text_parts.append(text_value)
                merged = "\n".join(part for part in text_parts if part.strip()).strip()
                if merged:
                    return merged

    output = response_json.get("output")
    if isinstance(output, dict):
        output_choices = output.get("choices")
        if isinstance(output_choices, list) and output_choices:
            message = output_choices[0].get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    return content.strip()
        output_text = output.get("text")
        if isinstance(output_text, str):
            return output_text.strip()

    return None


def generate_qa_answer(
    question: str,
    retrieval_hits: Sequence[RetrievalSearchHit],
    selected_anchor_payload: dict[str, Any] | None = None,
    history_messages: Sequence[dict[str, str]] | None = None,
) -> str:
    """调用 DashScope 聊天模型生成带证据边界的答案。"""
    api_key, base_url, model_name = _ensure_chat_configuration()

    system_prompt = (
        "你是论文学习助教。请严格基于给定证据回答。"
        "若证据不足，必须明确说明“证据不足”。"
        "回答时可使用 [1] [2] 形式引用证据编号，禁止虚构论文内容。"
    )

    context_block = _build_context_lines(retrieval_hits)
    anchor_block = json.dumps(selected_anchor_payload, ensure_ascii=False) if selected_anchor_payload else "无"
    user_prompt = (
        "【用户问题】\n"
        f"{question.strip()}\n\n"
        "【选区锚点】\n"
        f"{anchor_block}\n\n"
        "【检索证据】\n"
        f"{context_block if context_block else '无可用证据'}\n\n"
        "请输出简洁中文回答。若检索证据不足，直接说明证据不足，并给出下一步建议。"
    )

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    if history_messages:
        for item in history_messages[-8:]:
            role = item.get("role", "").strip()
            content = item.get("content", "").strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_prompt})

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.2,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url=base_url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=settings.dashscope_chat_timeout_sec) as response:
            raw_body = response.read()
    except HTTPError as exc:
        raw_error = exc.read().decode("utf-8", errors="ignore")
        raise LLMRequestError(f"模型请求失败：HTTP {exc.code} {raw_error}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise LLMRequestError("模型请求超时，请稍后重试。") from exc
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise LLMRequestError("模型请求超时，请稍后重试。") from exc
        raise LLMRequestError("模型服务不可达，请检查网络或配置。") from exc

    try:
        response_json = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LLMRequestError("模型响应不是合法 JSON。") from exc

    message_content = _extract_message_content(response_json)
    if not message_content:
        raise LLMRequestError("模型响应缺少可用内容。")
    return message_content
