"""
services/embeddings.py - safe text chunking and FAISS vector store management
"""
import pickle
import shutil
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from config import get_settings

settings = get_settings()
_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def clean_text(text: str) -> str:
    lines = []
    for line in text.replace("\x00", " ").splitlines():
        line = " ".join(line.split())
        if line:
            lines.append(line)
    cleaned = "\n".join(lines).strip()
    return cleaned[: settings.max_extract_chars]


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100, max_chunks: int = 400) -> list[str]:
    text = clean_text(text)
    if not text:
        return []

    chunk_size = max(300, int(chunk_size))
    overlap = max(0, min(int(overlap), chunk_size - 100))
    chunks: list[str] = []
    start = 0
    text_len = len(text)

    while start < text_len and len(chunks) < max_chunks:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end]

        if end < text_len:
            break_pos = max(chunk.rfind("\n"), chunk.rfind(". "), chunk.rfind(" "))
            if break_pos > chunk_size * 0.55:
                chunk = chunk[: break_pos + 1]
                end = start + len(chunk)

        chunk = chunk.strip()
        if chunk:
            chunks.append(chunk)

        next_start = end - overlap
        if next_start <= start:
            next_start = start + chunk_size
        start = next_start

    return chunks


def _index_dir(file_id: str) -> Path:
    d = Path(settings.faiss_index_dir) / file_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index_path(file_id: str) -> Path:
    return _index_dir(file_id) / "index.faiss"


def _chunks_path(file_id: str) -> Path:
    return _index_dir(file_id) / "chunks.pkl"


def build_index(file_id: str, chunks: list[str]) -> None:
    if not chunks:
        raise ValueError("No text chunks found for indexing.")

    model = get_embedding_model()
    embeddings = model.encode(chunks, show_progress_bar=False, batch_size=16, convert_to_numpy=True)
    embeddings = embeddings.astype(np.float32)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)

    faiss.write_index(index, str(_index_path(file_id)))
    with open(_chunks_path(file_id), "wb") as f:
        pickle.dump(chunks, f)


def search_index(file_id: str, query: str, top_k: int = 5) -> list[dict[str, Any]]:
    idx_path = _index_path(file_id)
    chk_path = _chunks_path(file_id)
    if not idx_path.exists() or not chk_path.exists():
        return []

    model = get_embedding_model()
    index = faiss.read_index(str(idx_path))
    with open(chk_path, "rb") as f:
        chunks: list[str] = pickle.load(f)

    q_emb = model.encode([query], convert_to_numpy=True).astype(np.float32)
    distances, indices = index.search(q_emb, min(top_k, len(chunks)))

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if 0 <= idx < len(chunks):
            results.append({"chunk": chunks[idx], "score": float(dist)})
    return results


def read_chunks(file_id: str, limit: int = 12) -> list[str]:
    chk_path = _chunks_path(file_id)
    if not chk_path.exists():
        return []
    with open(chk_path, "rb") as f:
        chunks: list[str] = pickle.load(f)
    return chunks[:limit]


def index_exists(file_id: str) -> bool:
    return _index_path(file_id).exists()


def delete_index(file_id: str) -> None:
    d = Path(settings.faiss_index_dir) / file_id
    if d.exists():
        shutil.rmtree(d)
