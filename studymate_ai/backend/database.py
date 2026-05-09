"""
database.py - Async SQLAlchemy engine and session factory
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import get_settings

settings = get_settings()
_db_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(_db_url, echo=False, pool_pre_ping=True, pool_size=10, max_overflow=20)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:  # type: ignore[override]
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    from models import AccessToken, ChatMessage, ChatSession, Flashcard, Quiz, QuizQuestion, Summary, UploadedFile, User  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight migration support for older local databases created before login/user support.
        for table in ["uploaded_files", "chat_messages", "quizzes", "flashcards"]:
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS user_id VARCHAR"))
        await conn.execute(text("ALTER TABLE summaries ADD COLUMN IF NOT EXISTS user_id VARCHAR"))
        await conn.execute(text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS session_id VARCHAR"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chat_messages_session_id ON chat_messages (session_id)"))
