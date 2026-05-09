"""
schemas.py - Pydantic request and response schemas
"""
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    full_name: str
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    token: str
    user: UserOut


class ModelSelectRequest(BaseModel):
    mode: str = "local"
    model: str


class ModelInfoResponse(BaseModel):
    mode: str
    model: str
    base_url: str
    local_models: list[str]
    cloud_models: list[str]


class FileOut(BaseModel):
    id: str
    filename: str
    original_name: str
    file_type: str
    file_size: int
    char_count: int
    chunk_count: int
    is_indexed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    file_id: str
    message: str
    session_id: str | None = None


class ChatSessionCreate(BaseModel):
    file_id: str


class ChatSessionOut(BaseModel):
    id: str
    file_id: str
    title: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageOut(BaseModel):
    id: str
    file_id: str
    session_id: str | None = None
    role: str
    content: str
    sources: list[Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    session_id: str
    user_message: ChatMessageOut
    assistant_message: ChatMessageOut


class SummaryRequest(BaseModel):
    file_id: str


class SummaryResponse(BaseModel):
    file_id: str
    summary: str


class QuizRequest(BaseModel):
    file_id: str
    num_questions: int = 5


class QuizQuestionOut(BaseModel):
    id: str
    question: str
    options: list[str]
    answer: str
    explanation: str | None = None

    model_config = {"from_attributes": True}


class QuizOut(BaseModel):
    id: str
    file_id: str
    title: str
    created_at: datetime
    questions: list[QuizQuestionOut]

    model_config = {"from_attributes": True}


class FlashcardRequest(BaseModel):
    file_id: str
    num_cards: int = 10


class FlashcardOut(BaseModel):
    id: str
    file_id: str
    front: str
    back: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FlashcardsResponse(BaseModel):
    file_id: str
    flashcards: list[FlashcardOut]
