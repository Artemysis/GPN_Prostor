import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user_optional, get_db
from app.db.models import ChatSession, Request, User
from app.schemas.chat import (
    ChatApplyRequest,
    ChatApplyResponse,
    ChatAutofillRequest,
    ChatAutofillResponse,
    ChatMessageCreate,
    ChatMessageOut,
    ChatSessionCreate,
    ChatSessionCreateOut,
    ChatSessionOut,
)
from app.services.autofill import apply_actions, autofill_from_session
from app.services.chat_agent import run_chat_turn
from app.utils.errors import NotFoundError, ValidationError

router = APIRouter()


async def _get_session(db: AsyncSession, session_id: uuid.UUID, with_messages: bool = True) -> ChatSession:
    stmt = select(ChatSession).where(ChatSession.id == session_id)
    if with_messages:
        stmt = stmt.options(selectinload(ChatSession.messages))
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session is None:
        raise NotFoundError("Чат-сессия не найдена")
    return session


@router.post("/chat/sessions", response_model=ChatSessionCreateOut, status_code=201)
async def create_chat_session(
    body: ChatSessionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_optional),
):
    session = ChatSession(request_id=body.request_id, user_id=user.id, title=body.title)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return ChatSessionCreateOut(session_id=session.id)


@router.get("/chat/sessions/{session_id}", response_model=ChatSessionOut)
async def get_chat_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    session = await _get_session(db, session_id)
    return ChatSessionOut(
        session_id=session.id,
        request_id=session.request_id,
        messages=[ChatMessageOut.model_validate(m) for m in session.messages],
    )


@router.get("/chat/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
async def get_chat_messages(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    session = await _get_session(db, session_id)
    return [ChatMessageOut.model_validate(m) for m in session.messages]


@router.post("/chat/sessions/{session_id}/messages")
async def post_chat_message(session_id: uuid.UUID, body: ChatMessageCreate, db: AsyncSession = Depends(get_db)):
    session = await _get_session(db, session_id)
    request_context = None
    if session.request_id:
        request = await db.get(Request, session.request_id)
        if request:
            request_context = {"title": request.title, "company_id": request.company_id, "product_id": request.product_id}

    generator = run_chat_turn(db, session, body.content, request_context)
    return StreamingResponse(generator, media_type="text/event-stream")


@router.post("/chat/sessions/{session_id}/autofill", response_model=ChatAutofillResponse)
async def autofill_session(session_id: uuid.UUID, body: ChatAutofillRequest, db: AsyncSession = Depends(get_db)):
    session = await _get_session(db, session_id)
    if session.request_id is None:
        raise ValidationError("У чат-сессии не привязана заявка")
    request = await db.get(Request, session.request_id)
    if request is None:
        raise NotFoundError("Заявка не найдена")
    result = await autofill_from_session(db, session, request, body.actions)
    return ChatAutofillResponse(**result)


@router.post("/chat/sessions/{session_id}/apply", response_model=ChatApplyResponse)
async def apply_session_actions(session_id: uuid.UUID, body: ChatApplyRequest, db: AsyncSession = Depends(get_db)):
    session = await _get_session(db, session_id, with_messages=False)
    if session.request_id is None:
        raise ValidationError("У чат-сессии не привязана заявка")
    request = await db.get(Request, session.request_id)
    if request is None:
        raise NotFoundError("Заявка не найдена")
    applied = await apply_actions(db, request, body.actions)
    return ChatApplyResponse(applied=applied)


@router.delete("/chat/sessions/{session_id}", status_code=204)
async def delete_chat_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    session = await _get_session(db, session_id, with_messages=False)
    await db.delete(session)
    await db.commit()
