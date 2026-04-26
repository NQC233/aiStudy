from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.note import NoteDeleteResponse, NoteItemResponse, UpdateNoteRequest
from app.services import delete_note, update_note

router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.patch(
    "/{note_id}",
    response_model=NoteItemResponse,
    summary="更新笔记内容",
)
def update_note_endpoint(
    note_id: str,
    payload: UpdateNoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteItemResponse:
    """更新标题或内容，不改动锚点绑定。"""
    return update_note(
        db=db,
        note_id=note_id,
        user_id=current_user.id,
        payload=payload,
    )


@router.delete(
    "/{note_id}",
    response_model=NoteDeleteResponse,
    summary="删除笔记",
)
def delete_note_endpoint(
    note_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteDeleteResponse:
    """删除笔记并保留其它笔记对同锚点的引用关系。"""
    return delete_note(
        db=db,
        note_id=note_id,
        user_id=current_user.id,
    )
