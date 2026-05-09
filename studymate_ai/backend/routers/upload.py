"""
routers/upload.py - File upload, listing, and deletion
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from config import get_settings
from database import get_db
from models import UploadedFile, User
from schemas import FileOut
from services.embeddings import build_index, chunk_text, delete_index
from services.extractor import extract_text

router = APIRouter(prefix="/files", tags=["files"])
settings = get_settings()

ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "text/plain": "txt",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}


@router.post("/upload", response_model=FileOut, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    mime = file.content_type or ""
    file_type = ALLOWED_TYPES.get(mime) or (ext if ext in {"pdf", "txt", "docx"} else None)
    if not file_type:
        raise HTTPException(status_code=400, detail="Unsupported file type. Upload PDF, TXT, or DOCX.")

    content = await file.read()
    size = len(content)
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if size > max_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_file_size_mb} MB limit.")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())
    saved_name = f"{file_id}.{file_type}"
    saved_path = upload_dir / saved_name
    saved_path.write_bytes(content)

    try:
        text = extract_text(saved_path, file_type)
    except Exception as e:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Text extraction failed: {e}")

    if not text.strip():
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="No readable text found in this file.")

    chunks = chunk_text(text)
    if not chunks:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Could not split this file into study chunks.")

    try:
        build_index(file_id, chunks)
        indexed = True
    except Exception as e:
        saved_path.unlink(missing_ok=True)
        delete_index(file_id)
        raise HTTPException(status_code=502, detail=f"Indexing failed: {e}")

    db_file = UploadedFile(
        id=file_id,
        user_id=current_user.id,
        filename=saved_name,
        original_name=file.filename or saved_name,
        file_type=file_type,
        file_size=size,
        char_count=len(text),
        chunk_count=len(chunks),
        is_indexed=indexed,
    )
    db.add(db_file)
    await db.commit()
    await db.refresh(db_file)
    return db_file


@router.get("/", response_model=list[FileOut])
async def list_files(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(UploadedFile)
        .where(UploadedFile.user_id == current_user.id)
        .order_by(UploadedFile.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{file_id}", response_model=FileOut)
async def get_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_file = await db.get(UploadedFile, file_id)
    if not db_file or db_file.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found.")
    return db_file


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_file = await db.get(UploadedFile, file_id)
    if not db_file or db_file.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found.")

    saved_path = Path(settings.upload_dir) / db_file.filename
    saved_path.unlink(missing_ok=True)
    delete_index(file_id)

    await db.delete(db_file)
    await db.commit()
