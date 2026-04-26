from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.asset import Asset
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.citation import Citation
from app.core.config import settings
from app.schemas.chat import (
    ChatMessageCitationItem,
    ChatMessageCreateRequest,
    ChatMessageCreateResponse,
    ChatMessageItem,
    ChatSessionCreateRequest,
    ChatSessionItem,
    ChatSessionMessagesResponse,
)
from app.services.asset_service import require_user_asset
from app.services.llm_service import LLMConfigurationError, LLMRequestError, generate_qa_answer
from app.services.retrieval_service import search_asset_chunks


def _require_asset(db: Session, asset_id: str) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到对应的学习资产。")
    return asset


def require_user_session(db: Session, session_id: str, user_id: str) -> ChatSession:
    statement = select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
    chat_session = db.scalars(statement).first()
    if chat_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到对应的问答会话。")
    return chat_session


def _normalize_session_title(asset: Asset, payload: ChatSessionCreateRequest) -> str:
    custom_title = (payload.title or "").strip()
    if custom_title:
        return custom_title[:255]
    default_title = f"{asset.title[:36]} 问答"
    return default_title.strip() or "论文问答会话"


def _to_citation_item(citation: Citation) -> ChatMessageCitationItem:
    return ChatMessageCitationItem(
        citation_id=citation.id,
        chunk_id=citation.chunk_id,
        score=citation.score,
        page_start=citation.page_start,
        page_end=citation.page_end,
        paragraph_start=citation.paragraph_start,
        paragraph_end=citation.paragraph_end,
        section_path=citation.section_path or [],
        block_ids=citation.block_ids or [],
        quote_text=citation.quote_text,
    )


def create_asset_chat_session(
    db: Session,
    asset_id: str,
    user_id: str,
    payload: ChatSessionCreateRequest,
) -> ChatSessionItem:
    asset = require_user_asset(db, asset_id, user_id)
    chat_session = ChatSession(
        asset_id=asset.id,
        user_id=user_id,
        title=_normalize_session_title(asset, payload),
    )
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)
    return ChatSessionItem(
        id=chat_session.id,
        asset_id=chat_session.asset_id,
        user_id=chat_session.user_id,
        title=chat_session.title,
        message_count=0,
        created_at=chat_session.created_at,
    )


def list_asset_chat_sessions(db: Session, asset_id: str, user_id: str) -> list[ChatSessionItem]:
    require_user_asset(db, asset_id, user_id)
    statement = (
        select(ChatSession, func.count(ChatMessage.id).label("message_count"))
        .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
        .where(ChatSession.asset_id == asset_id, ChatSession.user_id == user_id)
        .group_by(ChatSession.id)
        .order_by(ChatSession.created_at.desc())
    )
    rows = db.execute(statement).all()
    sessions: list[ChatSessionItem] = []
    for chat_session, message_count in rows:
        sessions.append(
            ChatSessionItem(
                id=chat_session.id,
                asset_id=chat_session.asset_id,
                user_id=chat_session.user_id,
                title=chat_session.title,
                message_count=int(message_count or 0),
                created_at=chat_session.created_at,
            )
        )
    return sessions


def list_chat_session_messages(db: Session, session_id: str, user_id: str) -> ChatSessionMessagesResponse:
    chat_session = require_user_session(db, session_id, user_id)
    statement = (
        select(ChatMessage)
        .options(selectinload(ChatMessage.citations))
        .where(ChatMessage.session_id == chat_session.id)
        .order_by(ChatMessage.created_at.asc())
    )
    message_rows = db.scalars(statement).all()

    messages: list[ChatMessageItem] = []
    for message in message_rows:
        ordered_citations = sorted(message.citations, key=lambda item: item.score, reverse=True)
        messages.append(
            ChatMessageItem(
                id=message.id,
                session_id=message.session_id,
                role=message.role,
                message_type=message.message_type,
                content=message.content,
                selection_anchor_payload=message.selection_anchor_payload,
                citations=[_to_citation_item(citation) for citation in ordered_citations],
                created_at=message.created_at,
            )
        )
    return ChatSessionMessagesResponse(session_id=chat_session.id, asset_id=chat_session.asset_id, messages=messages)


def _build_history_messages(
    db: Session,
    session_id: str,
    exclude_message_id: str,
    limit: int = 4,
) -> list[dict[str, str]]:
    statement = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id, ChatMessage.id != exclude_message_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    rows = list(db.scalars(statement).all())
    rows.reverse()

    history: list[dict[str, str]] = []
    for message in rows:
        if message.role not in {"user", "assistant"}:
            continue
        content = message.content.strip()
        if not content:
            continue
        history.append({"role": message.role, "content": content})
    return history


def create_chat_session_message(
    db: Session,
    session_id: str,
    user_id: str,
    payload: ChatMessageCreateRequest,
) -> ChatMessageCreateResponse:
    chat_session = require_user_session(db, session_id, user_id)
    asset = require_user_asset(db, chat_session.asset_id, user_id)

    if asset.kb_status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前资产知识库未就绪，请先完成知识库构建后再提问。",
        )

    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="question 不能为空。")

    selected_anchor_payload: dict[str, Any] | None = None
    if payload.selected_anchor is not None:
        selected_anchor_payload = payload.selected_anchor.model_dump(exclude_none=True)

    question_message = ChatMessage(
        session_id=chat_session.id,
        role="user",
        message_type="qa",
        content=question,
        selection_anchor_payload=selected_anchor_payload,
    )
    db.add(question_message)
    db.commit()
    db.refresh(question_message)

    retrieval = search_asset_chunks(
        db,
        asset.id,
        question,
        payload.top_k,
        rewrite_query=payload.rewrite_query,
        strategy=payload.strategy,
        user_id=user_id,
    )
    retrieval_hits = retrieval.results

    if retrieval_hits:
        try:
            answer = generate_qa_answer(
                question=question,
                retrieval_hits=retrieval_hits,
                selected_anchor_payload=selected_anchor_payload,
                history_messages=_build_history_messages(
                    db,
                    session_id=chat_session.id,
                    exclude_message_id=question_message.id,
                    limit=max(0, settings.qa_history_max_messages),
                ),
            )
        except (LLMConfigurationError, LLMRequestError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"模型服务暂不可用：{exc}",
            ) from exc
    else:
        answer = "当前检索结果未覆盖你的问题，证据不足以支持可靠回答。请尝试提供更具体的术语、页码或选中文本。"

    answer_message = ChatMessage(
        session_id=chat_session.id,
        role="assistant",
        message_type="qa",
        content=answer,
        selection_anchor_payload=selected_anchor_payload,
    )
    db.add(answer_message)
    db.flush()

    for hit in retrieval_hits:
        db.add(
            Citation(
                message_id=answer_message.id,
                asset_id=asset.id,
                chunk_id=hit.chunk_id,
                score=hit.score,
                page_start=hit.page_start,
                page_end=hit.page_end,
                paragraph_start=hit.paragraph_start,
                paragraph_end=hit.paragraph_end,
                section_path=hit.section_path,
                block_ids=hit.block_ids,
                quote_text=hit.quote_text,
            )
        )

    db.commit()

    citation_statement = (
        select(Citation)
        .where(Citation.message_id == answer_message.id)
        .order_by(Citation.score.desc())
    )
    citation_rows = db.scalars(citation_statement).all()

    return ChatMessageCreateResponse(
        session_id=chat_session.id,
        question_message_id=question_message.id,
        answer_message_id=answer_message.id,
        answer=answer_message.content,
        citations=[_to_citation_item(citation) for citation in citation_rows],
    )
