"""
main.py - StudyMate AI FastAPI application entry point
"""
import sys
from pathlib import Path
from contextlib import asynccontextmanager

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import get_settings
from database import init_db
from routers import auth, upload, chat, summary, quiz, flashcards
from schemas import ModelInfoResponse, ModelSelectRequest
from services.llm import check_connection, list_cloud_models
from services.model_state import get_active_base_url, get_active_mode, get_active_model, set_active_model

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.faiss_index_dir).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="StudyMate AI",
    description="AI-powered study assistant with RAG, quizzes, flashcards, summaries, and user accounts.",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(summary.router, prefix="/api")
app.include_router(quiz.router, prefix="/api")
app.include_router(flashcards.router, prefix="/api")


@app.get("/api/model-info", response_model=ModelInfoResponse, tags=["utility"])
async def model_info():
    cloud_models = await list_cloud_models()
    return ModelInfoResponse(
        mode=get_active_mode(),
        model=get_active_model(),
        base_url=get_active_base_url(),
        local_models=settings.local_models_list,
        cloud_models=cloud_models,
    )


@app.post("/api/model-select", response_model=ModelInfoResponse, tags=["utility"])
async def model_select(payload: ModelSelectRequest):
    try:
        state = set_active_model(payload.mode, payload.model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    cloud_models = await list_cloud_models()
    return ModelInfoResponse(
        mode=state.mode,
        model=state.model,
        base_url=get_active_base_url(),
        local_models=settings.local_models_list,
        cloud_models=cloud_models,
    )


@app.get("/api/health", tags=["utility"])
async def health():
    llm_status = await check_connection()
    return {"status": "ok", "llm": llm_status, "model": get_active_model(), "mode": get_active_mode()}


frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        return FileResponse(str(frontend_dir / "index.html"))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        file = frontend_dir / full_path
        if file.exists() and file.is_file():
            return FileResponse(str(file))
        return FileResponse(str(frontend_dir / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
