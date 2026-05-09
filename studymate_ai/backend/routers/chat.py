"""
routers/chat.py - Chat with uploaded notes, with separate chat sessions per note.
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from database import get_db
from models import ChatMessage, ChatSession, UploadedFile, User
from schemas import ChatMessageOut, ChatRequest, ChatResponse, ChatSessionCreate, ChatSessionOut
from services.rag import rag_chat

router = APIRouter(prefix="/chat", tags=["chat"])


def _make_title(message: str | None = None) -> str:
    if not message:
        return "New chat"
    clean = " ".join(message.split())
    return clean[:45] + ("..." if len(clean) > 45 else "")


async def _get_owned_file(file_id: str, current_user: User, db: AsyncSession) -> UploadedFile:
    db_file = await db.get(UploadedFile, file_id)
    if not db_file or db_file.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found.")
    return db_file


async def _get_owned_session(session_id: str, file_id: str, current_user: User, db: AsyncSession) -> ChatSession:
    session = await db.get(ChatSession, session_id)
    if not session or session.user_id != current_user.id or session.file_id != file_id:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    return session


async def _create_session(file_id: str, current_user: User, db: AsyncSession, title: str = "New chat") -> ChatSession:
    session = ChatSession(id=str(uuid.uuid4()), user_id=current_user.id, file_id=file_id, title=title)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def _attach_old_messages_to_session(file_id: str, current_user: User, db: AsyncSession) -> None:
    old_result = await db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.file_id == file_id,
            ChatMessage.user_id == current_user.id,
            ChatMessage.session_id.is_(None),
        )
        .order_by(ChatMessage.created_at.asc())
    )
    old_messages = old_result.scalars().all()
    if not old_messages:
        return
    session = ChatSession(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        file_id=file_id,
        title="Previous saved chat",
    )
    db.add(session)
    await db.flush()
    await db.execute(
        update(ChatMessage)
        .where(
            ChatMessage.file_id == file_id,
            ChatMessage.user_id == current_user.id,
            ChatMessage.session_id.is_(None),
        )
        .values(session_id=session.id)
    )
    await db.commit()


@router.post("/sessions", response_model=ChatSessionOut)
async def create_session(
    req: ChatSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_owned_file(req.file_id, current_user, db)
    return await _create_session(req.file_id, current_user, db)


@router.get("/sessions/{file_id}", response_model=list[ChatSessionOut])
async def list_sessions(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_owned_file(file_id, current_user, db)
    await _attach_old_messages_to_session(file_id, current_user, db)
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.file_id == file_id, ChatSession.user_id == current_user.id)
        .order_by(ChatSession.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_owned_file(req.file_id, current_user, db)

    if req.session_id:
        session = await _get_owned_session(req.session_id, req.file_id, current_user, db)
    else:
        session = await _create_session(req.file_id, current_user, db, _make_title(req.message))

    answer, sources = await rag_chat(req.file_id, req.message)

    if session.title == "New chat":
        session.title = _make_title(req.message)

    user_msg = ChatMessage(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        file_id=req.file_id,
        session_id=session.id,
        role="user",
        content=req.message,
    )
    assistant_msg = ChatMessage(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        file_id=req.file_id,
        session_id=session.id,
        role="assistant",
        content=answer,
        sources=sources,
    )
    db.add_all([user_msg, assistant_msg])
    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(assistant_msg)
    return ChatResponse(session_id=session.id, user_message=user_msg, assistant_message=assistant_msg)


@router.get("/history/{file_id}", response_model=list[ChatMessageOut])
async def history(
    file_id: str,
    session_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_owned_file(file_id, current_user, db)
    conditions = [ChatMessage.file_id == file_id, ChatMessage.user_id == current_user.id]
    if session_id:
        await _get_owned_session(session_id, file_id, current_user, db)
        conditions.append(ChatMessage.session_id == session_id)
    else:
        conditions.append(ChatMessage.session_id.is_(None))
    result = await db.execute(select(ChatMessage).where(*conditions).order_by(ChatMessage.created_at.asc()))
    return result.scalars().all()


@router.delete("/history/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def clear_history(
    file_id: str,
    session_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_owned_file(file_id, current_user, db)
    conditions = [ChatMessage.file_id == file_id, ChatMessage.user_id == current_user.id]
    if session_id:
        await _get_owned_session(session_id, file_id, current_user, db)
        conditions.append(ChatMessage.session_id == session_id)
    await db.execute(delete(ChatMessage).where(*conditions))
    await db.commit()
