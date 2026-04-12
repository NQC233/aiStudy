from __future__ import annotations

import json
import re
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
    max_hits = max(1, settings.qa_context_max_hits)
    max_chars = max(200, settings.qa_context_chars_per_hit)
    for index, hit in enumerate(retrieval_hits[:max_hits], start=1):
        section_label = (
            " / ".join(hit.section_path) if hit.section_path else "未标注章节"
        )
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
                    f"text={_clip_text(hit.text, limit=max_chars)}",
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
    anchor_block = (
        json.dumps(selected_anchor_payload, ensure_ascii=False)
        if selected_anchor_payload
        else "无"
    )
    user_prompt = (
        "【用户问题】\n"
        f"{question.strip()}\n\n"
        "【选区锚点】\n"
        f"{anchor_block}\n\n"
        "【检索证据】\n"
        f"{context_block if context_block else '无可用证据'}\n\n"
        "请输出简洁中文回答（不超过60字）。若检索证据不足，直接说明证据不足，并给出下一步建议。"
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
        "max_tokens": settings.qa_answer_max_tokens,
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


def generate_retrieval_query_rewrite(query: str) -> str:
    """将中文问题重写为英文检索表达，便于向量检索召回。"""
    api_key, base_url, model_name = _ensure_chat_configuration()

    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You rewrite Chinese academic questions into concise English retrieval queries. "
                    "Output plain text only. Keep key technical terms. No explanations."
                ),
            },
            {
                "role": "user",
                "content": query.strip(),
            },
        ],
        "temperature": 0.0,
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
        raise LLMRequestError(f"查询重写失败：HTTP {exc.code} {raw_error}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise LLMRequestError("查询重写超时，请稍后重试。") from exc
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise LLMRequestError("查询重写超时，请稍后重试。") from exc
        raise LLMRequestError("查询重写服务不可达，请检查网络或配置。") from exc

    try:
        response_json = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LLMRequestError("查询重写响应不是合法 JSON。") from exc

    message_content = _extract_message_content(response_json)
    if not message_content:
        raise LLMRequestError("查询重写响应缺少可用内容。")
    return message_content


def _build_slides_stage_prompt(
    stage: str,
    title: str,
    goal: str,
    script: str,
    evidence_quotes: Sequence[str],
) -> str:
    evidence_lines = [
        f"[{index}] {_clip_text(quote, limit=240)}"
        for index, quote in enumerate(evidence_quotes, start=1)
        if quote.strip()
    ]
    evidence_block = "\n".join(evidence_lines) if evidence_lines else "[1] 无可用证据"
    return (
        "你是论文演示文稿编辑器。请基于证据生成单页内容，不得虚构事实。\n"
        "输出必须是 JSON 对象，字段为：title,goal,script,evidence,key_points,evidence_list,takeaway。\n"
        "约束：title<=24字，goal<=42字，script<=180字，evidence<=160字，"
        "key_points 为 2~4 条、每条<=32字，evidence_list 为 1~2 条、每条<=60字，takeaway<=42字。\n"
        "\n"
        f"stage={stage}\n"
        f"原始标题={title}\n"
        f"原始目标={goal}\n"
        f"原始讲稿={script}\n"
        "证据列表：\n"
        f"{evidence_block}\n"
    )


def _extract_json_object(raw_text: str) -> dict[str, Any]:
    stripped = raw_text.strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise LLMRequestError("模型返回中缺少 JSON 对象。")
    snippet = stripped[start : end + 1]
    try:
        payload = json.loads(snippet)
    except json.JSONDecodeError as exc:
        repaired = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", snippet)
        try:
            payload = json.loads(repaired)
        except json.JSONDecodeError as repaired_exc:
            raise LLMRequestError("模型返回 JSON 解析失败。") from repaired_exc
    if not isinstance(payload, dict):
        raise LLMRequestError("模型返回 JSON 结构非法。")
    return payload


def generate_slides_stage_copy(
    stage: str,
    title: str,
    goal: str,
    script: str,
    evidence_quotes: Sequence[str],
) -> dict[str, str]:
    """调用 DashScope 生成单页讲稿文案（严格 JSON 输出）。"""
    api_key, base_url, model_name = _ensure_chat_configuration()

    system_prompt = (
        "你是严谨的论文讲稿编辑助手。"
        "必须严格基于证据，不允许添加证据外事实。"
        "输出仅允许 JSON 对象。"
    )
    user_prompt = _build_slides_stage_prompt(
        stage=stage,
        title=title,
        goal=goal,
        script=script,
        evidence_quotes=evidence_quotes,
    )

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    request = Request(
        url=base_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
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
    data = _extract_json_object(message_content)

    normalized_title = str(data.get("title", title)).strip() or title
    normalized_goal = str(data.get("goal", goal)).strip() or goal
    normalized_script = str(data.get("script", script)).strip() or script
    evidence_default = "；".join([quote for quote in evidence_quotes if quote.strip()])
    normalized_evidence = (
        str(data.get("evidence", evidence_default)).strip() or evidence_default
    )

    def _normalize_list(raw_value: Any, fallback_items: Sequence[str], max_items: int) -> list[str]:
        if isinstance(raw_value, list):
            normalized = [str(item).strip() for item in raw_value if str(item).strip()]
            if normalized:
                return normalized[:max_items]
        fallback = [item.strip() for item in fallback_items if item and item.strip()]
        return fallback[:max_items]

    normalized_key_points = _normalize_list(
        data.get("key_points"),
        [goal],
        max_items=4,
    )
    if len(normalized_key_points) < 2:
        normalized_key_points = [*normalized_key_points, _clip_text(normalized_evidence, limit=32)]
    normalized_key_points = [
        _clip_text(point, limit=32)
        for point in normalized_key_points[:4]
        if point.strip()
    ]

    normalized_evidence_list = _normalize_list(
        data.get("evidence_list"),
        [normalized_evidence],
        max_items=2,
    )
    normalized_evidence_list = [
        _clip_text(item, limit=60)
        for item in normalized_evidence_list
        if item.strip()
    ]

    normalized_takeaway = str(data.get("takeaway", "")).strip()
    if not normalized_takeaway:
        normalized_takeaway = normalized_goal or "总结结论并回扣论文主线。"

    return {
        "title": _clip_text(normalized_title, limit=24),
        "goal": _clip_text(normalized_goal, limit=42),
        "script": _clip_text(normalized_script, limit=180),
        "evidence": _clip_text(normalized_evidence, limit=160),
        "key_points": normalized_key_points,
        "evidence_list": normalized_evidence_list,
        "takeaway": _clip_text(normalized_takeaway, limit=42),
    }


def generate_slides_director_hint(page: Any) -> dict[str, str]:
    """调用 LLM 为单页生成布局和动画提示。"""
    api_key, base_url, model_name = _ensure_chat_configuration()
    page_type = str(getattr(page, "page_type", "topic"))
    title = str(getattr(page, "title", ""))
    key_points = getattr(page, "key_points", []) or []
    evidence = getattr(page, "evidence", []) or []

    user_prompt = (
        "你是 Reveal.js 演示导演。必须满足 frontend-slides 风格约束：\n"
        "1) 单页信息必须可在一个视口内读完（禁止滚动）\n"
        "2) 一页最多 4 条 key_points 与 2 条 evidence\n"
        "3) 视觉风格要有区分度，避免所有页同质化\n"
        "返回 JSON 对象，字段仅包含 layout_hint, animation_type, target_block_type, visual_tone。\n"
        "layout_hint 可选：hero-left, split-evidence, insight-stack, data-table, process-steps, visual-focus, closing-cta。\n"
        "animation_type 可选：stagger_reveal, focus_emphasis, compare_switch, flow_step。\n"
        "target_block_type 可选：key_points, evidence, comparison, flow, diagram_svg, takeaway。\n"
        "visual_tone 可选：editorial, technical, spotlight, warm。\n"
        f"page_type={page_type}\n"
        f"title={title}\n"
        f"key_points={json.dumps(key_points, ensure_ascii=False)}\n"
        f"evidence={json.dumps(evidence, ensure_ascii=False)}\n"
    )

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "你是严谨的演示设计助手，输出必须是 JSON。"},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    request = Request(
        url=base_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
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
        raise LLMRequestError(f"布局规划请求失败：HTTP {exc.code} {raw_error}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise LLMRequestError("布局规划超时，请稍后重试。") from exc
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise LLMRequestError("布局规划超时，请稍后重试。") from exc
        raise LLMRequestError("布局规划服务不可达，请检查网络或配置。") from exc

    try:
        response_json = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LLMRequestError("布局规划响应不是合法 JSON。") from exc

    message_content = _extract_message_content(response_json)
    if not message_content:
        raise LLMRequestError("布局规划响应缺少可用内容。")
    data = _extract_json_object(message_content)

    return {
        "layout_hint": str(data.get("layout_hint", "")).strip(),
        "animation_type": str(data.get("animation_type", "")).strip(),
        "target_block_type": str(data.get("target_block_type", "")).strip(),
        "visual_tone": str(data.get("visual_tone", "")).strip(),
    }
