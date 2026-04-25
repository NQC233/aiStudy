from __future__ import annotations

import json
import re
import socket
from collections.abc import Callable
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


def _normalize_chat_completion_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def get_slides_model_config(task_name: str) -> dict[str, str]:
    api_key, base_url, fallback_model_name = _ensure_chat_configuration()
    task_to_model = {
        "analysis": settings.dashscope_slides_analysis_model_name,
        "vision": settings.dashscope_slides_vision_model_name,
        "html": settings.dashscope_slides_html_model_name,
        "image": settings.dashscope_image_model_name,
    }
    model_name = task_to_model.get(task_name, "").strip() or fallback_model_name
    if task_name == "image":
        return {
            "api_key": api_key,
            "base_url": settings.dashscope_image_base_url or base_url,
            "model_name": model_name,
        }
    return {
        "api_key": api_key,
        "base_url": base_url,
        "model_name": model_name,
    }


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


def describe_visual_asset(
    asset_payload: dict[str, Any],
    *,
    model_caller: Callable[[str, dict[str, Any]], dict[str, str]] | None = None,
) -> dict[str, str]:
    if model_caller is not None:
        prompt = (
            "Describe this paper visual asset for slide planning. "
            "Return concise structured fields."
        )
        return model_caller(prompt, asset_payload)

    caption_text = str(asset_payload.get("caption_text", "")).strip()
    asset_type = str(asset_payload.get("asset_type", "")).strip() or "visual"
    surrounding_context = str(asset_payload.get("surrounding_context", "")).strip()
    summary = caption_text or surrounding_context or f"{asset_type} asset"
    recommended_usage = (
        "results_comparison" if asset_type == "table" else "general_visual"
    )
    return {
        "vision_summary": summary,
        "what_this_asset_shows": summary,
        "why_it_matters": surrounding_context or summary,
        "best_scene_role": "results" if asset_type == "table" else "method",
        "recommended_usage": recommended_usage,
        "reuse_priority": "medium",
    }


def _call_slides_json_model(
    *,
    task_name: str,
    system_prompt: str,
    user_payload: dict[str, Any],
    model_caller: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if model_caller is not None:
        return model_caller(system_prompt, user_payload)

    model_config = get_slides_model_config(task_name)
    timeout_by_task = {
        "analysis": settings.dashscope_slides_planner_timeout_sec,
        "scene": settings.dashscope_slides_scene_timeout_sec,
        "html": settings.dashscope_slides_html_timeout_sec,
    }
    request_timeout = timeout_by_task.get(task_name, settings.dashscope_slides_timeout_sec)
    payload = {
        "model": model_config["model_name"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    request = Request(
        url=_normalize_chat_completion_url(model_config["base_url"]),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {model_config['api_key']}",
            "Content-Type": "application/json",
        },
    )
    
    try:
        with urlopen(request, timeout=request_timeout) as response:
            raw_body = response.read()
    except HTTPError as exc:
        raw_error = exc.read().decode("utf-8", errors="ignore")
        raise LLMRequestError(f"slides 模型请求失败：HTTP {exc.code} {raw_error}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise LLMRequestError("slides 模型请求超时，请稍后重试。") from exc
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise LLMRequestError("slides 模型请求超时，请稍后重试。") from exc
        raise LLMRequestError("slides 模型服务不可达，请检查网络或配置。") from exc

    try:
        response_json = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LLMRequestError("slides 模型响应不是合法 JSON。") from exc

    message_content = _extract_message_content(response_json)
    if not message_content:
        raise LLMRequestError("slides 模型响应缺少可用内容。")
    return _extract_json_object(message_content)


def generate_slides_presentation_plan(
    analysis_pack: dict[str, Any],
    visual_asset_catalog: list[dict[str, object]],
    *,
    model_caller: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    raw = _call_slides_json_model(
        task_name="analysis",
        system_prompt=(
            "你是一名论文转演示文稿的总导演，负责把论文分析结果规划成适合课堂讲解的完整中文演示稿。"
            "只返回 JSON，对象顶层必须包含 page_count 和 pages。"
            "pages 中每一页都必须包含 page_id、scene_role、narrative_goal、content_focus、"
            "visual_strategy、candidate_assets、animation_intent。"
            "所有面向用户的字段都必须使用中文（中文），不要直接复用英文原文长句。"
            "如果 analysis_pack 信息丰富，页数至少 8 页；长论文可以更多，上限由你自行判断，但必须保证讲解完整。"
            "严禁退化成 4 页概述、单页 overview、或简单按字段名做机械分页。"
            "必须优先覆盖：问题背景、方法概览、关键机制、训练/实现细节、主实验结果、对比/消融、局限性、总结。"
            "每一页的 narrative_goal 必须是中文讲解目标，而不是英文摘录。"
            "优秀示例：一篇结构完整的方法论文，通常会规划成 8-12 页，例如“问题背景、方法总览、关键机制一、关键机制二、训练细节、主结果、消融分析、局限与总结”。"
        ),
        user_payload={
            "analysis_pack": analysis_pack,
            "visual_asset_catalog": visual_asset_catalog,
        },
        model_caller=model_caller,
    )
    pages = raw.get("pages") if isinstance(raw.get("pages"), list) else []
    normalized_pages: list[dict[str, Any]] = []
    for index, page in enumerate(pages, start=1):
        if not isinstance(page, dict):
            continue
        candidate_assets = page.get("candidate_assets")
        normalized_pages.append(
            {
                "page_id": str(page.get("page_id", f"page-{index}")).strip() or f"page-{index}",
                "scene_role": str(page.get("scene_role", "overview")).strip() or "overview",
                "narrative_goal": str(page.get("narrative_goal", "Paper Overview")).strip() or "Paper Overview",
                "content_focus": str(page.get("content_focus", "overview")).strip() or "overview",
                "visual_strategy": str(page.get("visual_strategy", "text_only")).strip() or "text_only",
                "candidate_assets": [
                    str(item).strip()
                    for item in candidate_assets
                    if str(item).strip()
                ]
                if isinstance(candidate_assets, list)
                else [],
                "animation_intent": str(page.get("animation_intent", "soft_intro")).strip() or "soft_intro",
            }
        )
    return {
        "page_count": int(raw.get("page_count", len(normalized_pages) or 1)),
        "pages": normalized_pages,
    }


def generate_slide_scene_spec(
    page: dict[str, Any],
    analysis_pack: dict[str, Any],
    visual_asset_catalog: list[dict[str, object]],
    *,
    deck_style_guide: dict[str, Any] | None = None,
    model_caller: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    raw = _call_slides_json_model(
        task_name="scene",
        system_prompt=(
            "你负责把单页导演计划扩展成逐页 scene_spec。只返回 JSON，必须包含 title、summary_line、layout_strategy、"
            "content_blocks、citations、asset_bindings、animation_plan、speaker_note_seed。"
            "所有对用户可见的文案都必须使用中文（中文），即使证据是英文。"
            "content_blocks 不能为空，citations 也不能为空；如果没有证据就说明 scene 不成立。"
            "不要把 page.narrative_goal 直接重复成 title 和 summary_line。"
            "必须从 analysis_pack 中挑选与该页最相关的证据，写成具体可展示的页面内容。"
            "优先输出有证据支撑的要点、对比、公式、指标、图表解读和资产说明。"
            "优秀示例：方法页通常会包含 3-5 条有层次的 bullets、1-2 个 citations、必要时绑定 figure/table，而不是只有标题和一句摘要。"
            "同一份 deck 内所有页面必须遵守同一套 deck_style_guide，保证主题、字体、色彩、版心和引用样式一致。"
        ),
        user_payload={
            "page": page,
            "analysis_pack": analysis_pack,
            "visual_asset_catalog": visual_asset_catalog,
            "deck_style_guide": deck_style_guide or {},
        },
        model_caller=model_caller,
    )
    return {
        "page_id": str(page.get("page_id", "page-1")),
        "title": str(raw.get("title", page.get("narrative_goal", "Paper Overview"))).strip() or "Paper Overview",
        "summary_line": str(raw.get("summary_line", page.get("narrative_goal", ""))).strip(),
        "layout_strategy": str(raw.get("layout_strategy", "hero-text")).strip() or "hero-text",
        "content_blocks": raw.get("content_blocks") if isinstance(raw.get("content_blocks"), list) else [],
        "citations": raw.get("citations") if isinstance(raw.get("citations"), list) else [],
        "asset_bindings": raw.get("asset_bindings") if isinstance(raw.get("asset_bindings"), list) else [],
        "animation_plan": raw.get("animation_plan") if isinstance(raw.get("animation_plan"), dict) else {"type": "soft_intro"},
        "speaker_note_seed": str(raw.get("speaker_note_seed", page.get("narrative_goal", ""))).strip(),
    }


def _normalize_batch_html_page(page: dict[str, Any], index: int) -> dict[str, Any]:
    if not isinstance(page.get("page_id"), str) or not str(page.get("page_id", "")).strip():
        raise ValueError("batch html response missing page_id field")
    if not isinstance(page.get("html"), str) or not isinstance(page.get("css"), str):
        raise ValueError("batch html response missing html/css fields")
    if not isinstance(page.get("render_meta"), dict):
        raise ValueError("batch html response missing render_meta field")
    return {
        "page_id": str(page["page_id"]).strip() or f"page-{index}",
        "html": page["html"].strip(),
        "css": page["css"].strip(),
        "render_meta": page["render_meta"],
    }



def generate_slide_html_bundle(
    scene_specs: list[dict[str, Any]],
    *,
    deck_style_guide: dict[str, Any] | None = None,
    deck_digest: dict[str, Any] | None = None,
    deck_meta: dict[str, Any] | None = None,
    model_caller: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    canvas_width = settings.slides_html_canvas_width
    canvas_height = settings.slides_html_canvas_height
    raw = _call_slides_json_model(
        task_name="html",
        system_prompt=(
            "你负责一次性渲染整套多页 HTML 演示稿。只返回 JSON，顶层必须包含 deck_meta 和 pages。"
            "pages 必须是逐页数组；不要返回长文档，不要把整套内容拼成一个连续页面。"
            "pages 数组中的每一页都必须是完整的 page-level HTML payload，且必须同时包含 page_id、html、css、render_meta 四个字段。"
            "每一页都必须直接返回可渲染的 html 和 css，不要返回 layout、elements、safe_area、outline、component plan 等中间设计稿字段来替代 html/css。"
            f"每一页都必须严格输出 1 张固定 {canvas_width}px × {canvas_height}px 的单页画布，比例严格为 16:9。"
            f"每一页的 html、body 和根画布容器都必须显式声明 width: {canvas_width}px; height: {canvas_height}px; margin: 0; padding: 0; overflow: hidden;。"
            "禁止使用 min-height: 100vh、height: auto、内容撑高页面、纵向堆叠无限增长、响应式长文布局。"
            "禁止 body 滚动、根容器滚动、内部容器滚动；首屏渲染时页面必须完整落入固定画布内。"
            "所有重要内容必须控制在安全区内：左右至少 80px，上方至少 64px，下方至少 56px。"
            "你需要直接输出最终可渲染 HTML，不要输出 placeholder、资产占位说明、Markdown 源标记或公式源码。"
            "如果 scene_specs 中存在 asset_bindings 或可复用视觉资产，应优先将其落成真实视觉结构，例如 <img>、<svg>、<table> 或其他最终 DOM。"
            "不得输出 placeholder、[图表占位]、[图片占位]、待补图片 等占位内容来替代真实视觉结构。"
            "Markdown 语法必须渲染成最终 HTML；公式必须渲染成最终可展示结构，不得直接输出 `$...$`、`$$...$$` 或未展开的 markdown 标记。"
            "除非 scene_specs 确实没有更丰富的内容，否则不要退化为 title+paragraph 式兜底布局。"
            "同一套 deck 的标题层级、正文密度、间距、引用样式必须统一。"
        ),
        user_payload={
            "scene_specs": scene_specs,
            "deck_style_guide": deck_style_guide or {},
            "deck_digest": deck_digest or {},
            "deck_meta": deck_meta or {},
        },
        model_caller=model_caller,
    )
    pages = raw.get("pages") if isinstance(raw.get("pages"), list) else []
    return {
        "deck_meta": raw.get("deck_meta") if isinstance(raw.get("deck_meta"), dict) else {},
        "pages": [
            _normalize_batch_html_page(page, index)
            for index, page in enumerate(pages, start=1)
            if isinstance(page, dict)
        ],
    }


def generate_slide_html_page(
    scene_spec: dict[str, Any],
    *,
    deck_style_guide: dict[str, Any] | None = None,
    model_caller: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    canvas_width = settings.slides_html_canvas_width
    canvas_height = settings.slides_html_canvas_height
    raw = _call_slides_json_model(
        task_name="html",
        system_prompt=(
            "你负责渲染单页 16:9 HTML 演示页。只返回 JSON，必须包含 html、css、render_meta。"
            "HTML 中所有可见文字都必须使用中文。"
            "这不是网页，不是文章，不是长文档，而是一张固定像素的演示幻灯片。"
            f"你必须严格输出 1 张固定 {canvas_width}px × {canvas_height}px 的单页画布，比例严格为 16:9。"
            f"html、body 和根画布容器都必须显式声明 width: {canvas_width}px; height: {canvas_height}px; margin: 0; padding: 0; overflow: hidden;。"
            "禁止使用 min-height: 100vh、height: auto、内容撑高页面、纵向堆叠无限增长、响应式长文布局。"
            "禁止 body 滚动、根容器滚动、内部容器滚动；首屏渲染时页面必须完整落入固定画布内。"
            "所有重要内容必须控制在安全区内：左右至少 80px，上方至少 64px，下方至少 56px。"
            "标题最多 2 行；导语最多 3 行；单个文本块最多 6 行；页面最多 3 个主要文本区域和 1 个主要视觉区域。"
            "如果内容过多，必须主动提炼、压缩、分组，而不是让容器变高或出现滚动条。"
            "除非 scene_spec 确实没有更丰富的内容，否则不要退化为 title+paragraph 式兜底布局。"
            "你需要把 content_blocks 展开成有层次、有重点、有视觉焦点的单页演示结构，在可用时应体现图表或资产绑定。"
            "优秀示例：结果页应至少包含标题区、指标/对比区、证据标注区；方法页应至少包含结构说明区和重点解释区，而不是只放一段文字。"
            "优秀页面必须同时满足：固定画布、无滚动、结构清晰、视觉平衡、主题统一。"
            "同一份 deck 内所有页面必须遵守同一套 deck_style_guide，保证主题、字体、颜色、间距和引用样式一致。"
            "如果提供了 deck_meta，你必须复用其中的 typography、spacing、tone、component rules，不得重新发明另一套风格。"
        ),
        user_payload={
            "scene_spec": scene_spec,
            "deck_style_guide": deck_style_guide or {},
            "deck_meta": (deck_style_guide or {}).get("deck_meta", {}),
        },
        model_caller=model_caller,
    )
    return {
        "page_id": str(scene_spec.get("page_id", "page-1")),
        "html": str(raw.get("html", "")).strip(),
        "css": str(raw.get("css", "")).strip(),
        "asset_refs": scene_spec.get("asset_bindings", []),
        "render_meta": raw.get("render_meta") if isinstance(raw.get("render_meta"), dict) else {},
    }


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
        url=_normalize_chat_completion_url(base_url),
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
