# StudyMate AI

A FastAPI web app for studying uploaded notes with RAG, summaries, quizzes, flashcards, local Ollama, official Ollama Cloud, and user login.

## What changed in this version

- Login and registration are included.
- Each user only sees their own files, chat history, summaries, quizzes, and flashcards.
- Local and cloud model switching is available in Settings.
- Official Ollama Cloud uses `https://ollama.com/api` with `OLLAMA_API_KEY`.
- The app tries to load all cloud models from `https://ollama.com/api/tags`.
- Quiz and flashcard generation now uses cleaner study text and validation.
- If a small local model gives poor JSON, the app uses a fallback generator so you do not get blank questions.
- PDF extraction and chunking are safer for larger PDFs.
- Docker is not needed.

## Setup

Create the PostgreSQL database in pgAdmin or Query Tool:

```sql
CREATE USER studymate WITH PASSWORD '1791962';
CREATE DATABASE studymate_db OWNER studymate;
GRANT ALL PRIVILEGES ON DATABASE studymate_db TO studymate;
```

Or use your existing `postgres` user and update `.env`.

## Environment

Copy `.env.example` to `.env`.

For local Ollama:

```env
OLLAMA_LOCAL_BASE_URL=http://localhost:11434
OLLAMA_LOCAL_MODEL=qwen2.5:0.5b
```

For official Ollama Cloud:

```env
OLLAMA_CLOUD_BASE_URL=https://ollama.com
OLLAMA_API_KEY=your_ollama_api_key_here
OLLAMA_CLOUD_MODEL=gpt-oss:20b
```

Do not put your real API key in `.env.example`.

## Install

From the project root:

```bash
cd backend
pip install -r requirements.txt
```

## Run

Start Ollama if you use local models:

```bash
ollama serve
```

Then start the app:

```bash
uvicorn main:app --reload
```

Open:

```txt
http://127.0.0.1:8000
```

## Better quiz and flashcard results

For best results, use a stronger cloud model from Settings. The local `qwen2.5:0.5b` model is small, so answers may be simpler.
