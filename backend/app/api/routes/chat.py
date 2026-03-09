from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.chat import (
    ChatMessageCreateRequest,
    ChatMessageCreateResponse,
    ChatSessionMessagesResponse,
)
from app.services import create_chat_session_message, list_chat_session_messages

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get(
    "/sessions/{session_id}/messages",
    response_model=ChatSessionMessagesResponse,
    summary="获取问答会话消息",
)
def list_chat_session_messages_endpoint(
    session_id: str,
    db: Session = Depends(get_db),
) -> ChatSessionMessagesResponse:
    """返回会话内全部消息和引用。"""
    return list_chat_session_messages(db, session_id)


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatMessageCreateResponse,
    summary="发送问题并生成回答",
)
def create_chat_session_message_endpoint(
    session_id: str,
    payload: ChatMessageCreateRequest,
    db: Session = Depends(get_db),
) -> ChatMessageCreateResponse:
    """执行单资产检索增强问答并持久化消息与引用。"""
    return create_chat_session_message(db, session_id, payload)
