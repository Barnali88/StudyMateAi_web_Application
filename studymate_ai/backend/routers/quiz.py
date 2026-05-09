"""
routers/quiz.py - Quiz generation and retrieval
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth import get_current_user
from config import get_settings
from database import get_db
from models import Quiz, QuizQuestion, UploadedFile, User
from schemas import QuizOut, QuizRequest
from services.extractor import extract_text
from services.rag import generate_quiz

router = APIRouter(prefix="/quiz", tags=["quiz"])
settings = get_settings()


async def _get_owned_file(file_id: str, current_user: User, db: AsyncSession) -> UploadedFile:
    db_file = await db.get(UploadedFile, file_id)
    if not db_file or db_file.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found.")
    return db_file


@router.post("/generate", response_model=QuizOut)
async def create_quiz(
    req: QuizRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_file = await _get_owned_file(req.file_id, current_user, db)
    file_path = Path(settings.upload_dir) / db_file.filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File data not found on disk.")

    try:
        text = extract_text(file_path, db_file.file_type)
        questions_data = await generate_quiz(text, num_questions=req.num_questions)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Quiz generation failed: {e}")

    if not questions_data:
        raise HTTPException(status_code=422, detail="Could not generate quiz questions. Try with a larger document.")

    quiz = Quiz(id=str(uuid.uuid4()), user_id=current_user.id, file_id=req.file_id, title=f"Quiz - {db_file.original_name}")
    db.add(quiz)
    await db.flush()

    for q in questions_data:
        db.add(QuizQuestion(
            id=str(uuid.uuid4()),
            quiz_id=quiz.id,
            question=q.get("question", ""),
            options=q.get("options", []),
            answer=q.get("answer", "A"),
            explanation=q.get("explanation"),
        ))

    await db.commit()
    result = await db.execute(select(Quiz).where(Quiz.id == quiz.id).options(selectinload(Quiz.questions)))
    return result.scalar_one()


@router.get("/{file_id}", response_model=list[QuizOut])
async def list_quizzes(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_owned_file(file_id, current_user, db)
    result = await db.execute(
        select(Quiz)
        .where(Quiz.file_id == file_id, Quiz.user_id == current_user.id)
        .options(selectinload(Quiz.questions))
        .order_by(Quiz.created_at.desc())
    )
    return result.scalars().all()


@router.delete("/{quiz_id}", status_code=204)
async def delete_quiz(
    quiz_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    quiz = await db.get(Quiz, quiz_id)
    if not quiz or quiz.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Quiz not found.")
    await db.delete(quiz)
    await db.commit()
