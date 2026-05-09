"""
routers/summary.py - Document summarisation
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from config import get_settings
from database import get_db
from models import Summary, UploadedFile, User
from schemas import SummaryRequest, SummaryResponse
from services.extractor import extract_text
from services.rag import summarise_text

router = APIRouter(prefix="/summary", tags=["summary"])
settings = get_settings()


async def _get_owned_file(file_id: str, current_user: User, db: AsyncSession) -> UploadedFile:
    db_file = await db.get(UploadedFile, file_id)
    if not db_file or db_file.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found.")
    return db_file


@router.post("/", response_model=SummaryResponse)
async def summarise(
    req: SummaryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_file = await _get_owned_file(req.file_id, current_user, db)
    file_path = Path(settings.upload_dir) / db_file.filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File data not found on disk.")

    try:
        text = extract_text(file_path, db_file.file_type)
        summary = await summarise_text(text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Summarisation failed: {e}")

    db.add(Summary(id=str(uuid.uuid4()), user_id=current_user.id, file_id=req.file_id, content=summary))
    await db.commit()
    return SummaryResponse(file_id=req.file_id, summary=summary)
