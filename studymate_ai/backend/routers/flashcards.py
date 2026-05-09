"""
routers/flashcards.py - Flashcard generation and retrieval
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from config import get_settings
from database import get_db
from models import Flashcard, UploadedFile, User
from schemas import FlashcardOut, FlashcardRequest, FlashcardsResponse
from services.extractor import extract_text
from services.rag import generate_flashcards

router = APIRouter(prefix="/flashcards", tags=["flashcards"])
settings = get_settings()


async def _get_owned_file(file_id: str, current_user: User, db: AsyncSession) -> UploadedFile:
    db_file = await db.get(UploadedFile, file_id)
    if not db_file or db_file.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found.")
    return db_file


@router.post("/generate", response_model=FlashcardsResponse)
async def create_flashcards(
    req: FlashcardRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_file = await _get_owned_file(req.file_id, current_user, db)
    file_path = Path(settings.upload_dir) / db_file.filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File data not found on disk.")

    try:
        text = extract_text(file_path, db_file.file_type)
        cards_data = await generate_flashcards(text, num_cards=req.num_cards)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flashcard generation failed: {e}")

    if not cards_data:
        raise HTTPException(status_code=422, detail="Could not generate flashcards. Try with a larger document.")

    saved_cards = []
    for c in cards_data:
        card = Flashcard(id=str(uuid.uuid4()), user_id=current_user.id, file_id=req.file_id, front=c.get("front", ""), back=c.get("back", ""))
        db.add(card)
        saved_cards.append(card)

    await db.commit()
    for card in saved_cards:
        await db.refresh(card)

    return FlashcardsResponse(file_id=req.file_id, flashcards=[FlashcardOut.model_validate(c) for c in saved_cards])


@router.get("/{file_id}", response_model=FlashcardsResponse)
async def list_flashcards(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_owned_file(file_id, current_user, db)
    result = await db.execute(
        select(Flashcard)
        .where(Flashcard.file_id == file_id, Flashcard.user_id == current_user.id)
        .order_by(Flashcard.created_at.asc())
    )
    cards = result.scalars().all()
    return FlashcardsResponse(file_id=file_id, flashcards=[FlashcardOut.model_validate(c) for c in cards])


@router.delete("/{file_id}/all", status_code=204)
async def delete_flashcards(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_owned_file(file_id, current_user, db)
    await db.execute(delete(Flashcard).where(Flashcard.file_id == file_id, Flashcard.user_id == current_user.id))
    await db.commit()
