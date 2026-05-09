# StudyMate AI

StudyMate AI is a simple AI study notes web application. Students can upload notes, chat with their files, generate summaries, create quizzes, and review flashcards. The app uses RAG with Ollama local or cloud models.

## Main Features

- User registration and login
- Private files for each user
- Upload PDF, TXT, and DOCX notes
- Chat with uploaded notes using RAG
- Generate study summaries
- Generate quizzes from notes
- Generate flashcards from notes
- Save chat, quiz, summary, and flashcard history
- Create new chat sessions for the same note
- Switch between local Ollama models and Ollama cloud models
- PostgreSQL database support

## Tech Stack

- Python 3.12
- FastAPI
- PostgreSQL
- SQLAlchemy
- Ollama
- Local LLM support
- Ollama cloud model support
- FAISS or local vector storage
- HTML, CSS, JavaScript frontend

## Project Purpose

Students often have long lecture notes and limited time to study. StudyMate AI helps students understand their notes faster by turning uploaded documents into a searchable AI study assistant.

The app is useful for:

- Exam preparation
- Lecture revision
- Quick note summaries
- Practice quiz generation
- Flashcard-based revision
- Asking questions from course materials

## How It Works

1. The user creates an account or logs in.
2. The user uploads a study file.
3. The app extracts text from the file.
4. The text is split into smaller chunks.
5. The chunks are indexed for RAG.
6. The user asks a question or generates study material.
7. The app retrieves relevant chunks.
8. Ollama generates the final answer using the retrieved content.
9. The app saves study history for the logged-in user.

## Folder Structure

```text
studymate_ai/
│
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── auth.py
│   ├── requirements.txt
│   ├── routers/
│   │   ├── auth.py
│   │   ├── chat.py
│   │   ├── files.py
│   │   ├── quiz.py
│   │   ├── summary.py
│   │   └── flashcards.py
│   └── services/
│       ├── embeddings.py
│       ├── file_parser.py
│       ├── llm.py
│       └── rag.py
│
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
│
├── database/
│   └── create_database.sql
│
├── uploads/
├── .env
├── .env.example
└── README.md
```

## Requirements

Before running the project, install:

- Python 3.12
- PostgreSQL
- Ollama
- PyCharm

## Database Setup

Open pgAdmin and create a database:

```sql
CREATE DATABASE studymate_db;
```

Use this format in your `.env` file:

```env
DATABASE_URL=postgresql+asyncpg://postgres:your_password@localhost:5432/studymate_db
```

## Environment Variables

Create a `.env` file in the project root.

Example:

```env
DATABASE_URL=postgresql+asyncpg://postgres:your_password@localhost:5432/studymate_db

OLLAMA_LOCAL_BASE_URL=http://localhost:11434
OLLAMA_LOCAL_MODEL=qwen2.5:0.5b

USE_CLOUD_MODEL=false
OLLAMA_API_KEY=your_ollama_api_key_here (Log in ollama app then connect your account, in browser; go to- your account> keys> generate api key)

DEFAULT_MODEL=qwen2.5:0.5b (Install the model that runs well in your personal computer)

MAX_FILE_SIZE_MB=50
```

Keep your real API key only inside `.env`.

Do not put real passwords or API keys inside `.env.example`.

## Ollama Setup in control panel

Start Ollama:

```bash
ollama serve
```

Pull the local model:

```bash
ollama pull qwen2.5:0.5b
```

Test the model:

```bash
ollama run qwen2.5:0.5b
```

For cloud models, sign in to Ollama and use your Ollama API key in `.env`.

## Installation

Go to the backend folder:

```bash
cd backend
```

Install packages:

```bash
pip install -r requirements.txt
```

## Run the Application

From the backend folder, run:

```bash
uvicorn main:app --reload
```

Open the app in your browser:

```text
http://127.0.0.1:8000
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

## Basic Usage

1. Register a new account.
2. Log in.
3. Upload a PDF, TXT, or DOCX file.
4. Click the note from My Notes.
5. Ask questions in Chat.
6. Generate a summary.
7. Generate quizzes.
8. Generate flashcards.
9. Start new chat sessions for the same note when needed.
10. Log back in later to see saved history.

## Key AI Features

### RAG Chat

The chatbot answers based on uploaded notes. It retrieves relevant chunks before sending the prompt to the model.

### Summary Generator

The app creates a study summary from the selected note.

### Quiz Generator

The app generates practice questions from the note and saves quiz history.

### Flashcard Generator

The app creates flashcards for revision and saves them for later study.

### Model Switching

The user can switch between:

- Local Ollama model
- Official Ollama cloud models

Local model example:

```text
qwen2.5:0.5b 
```

Cloud model examples depend on the models available in the Ollama account.


### Ollama not working

Make sure Ollama is running:

```bash
ollama serve
```

Then test:

```bash
ollama run qwen2.5:0.5b
```

### App logs in automatically

The app uses session-based browser storage. If needed, clear browser site data for:

```text
127.0.0.1:8000
```

### Cloud model error

Check:

- Ollama API key
- Internet connection
- Cloud model name
- Ollama account access

## Future Improvements

- Better quiz difficulty levels
- Note folders by subject
- Export summaries as PDF
- Student progress tracking
- Dark and light theme switch


## Project Status

StudyMate AI is a working educational AI project built for learning, portfolio use, and real-world study support.

## Author

Barnali Debnath

