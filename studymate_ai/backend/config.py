"""
config.py - central settings loaded from the project root .env file
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

DEFAULT_CLOUD_MODELS = ",".join([
    "minimax-m2.1",
    "minimax-m2.5",
    "minimax-m2.7",
    "gemini-3-flash-preview",
    "cogito-2.1:671b",
    "glm-4.6",
    "glm-5.1",
    "glm-4.7",
    "kimi-k2:1t",
    "kimi-k2-thinking",
    "kimi-k2.6",
    "qwen3-coder-next",
    "qwen3-next",
    "qwen3-coder:480b",
    "deepseek-v3.1:671b",
    "gpt-oss:20b",
    "gpt-oss:120b",
    "gemma3:4b",
    "gemma3:12b",
    "gemma3:27b",
    "gemma3:270m",
    "gemma4:31b",
    "mistral-3:8b",
    "mistral-3:14b",
    "mistral-large-3:675b",
    "devstral-2:123b",
])


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://studymate:1791962@localhost:5432/studymate_db"

    ollama_local_base_url: str = "http://localhost:11434"
    ollama_local_model: str = "qwen2.5:0.5b"
    ollama_local_models: str = "qwen2.5:0.5b,smollm2,gemma3:270m"

    use_cloud_model: bool = False
    ollama_cloud_base_url: str = "https://ollama.com"
    ollama_api_key: str = ""
    ollama_cloud_model: str = "gpt-oss:20b"
    ollama_cloud_models: str = DEFAULT_CLOUD_MODELS

    upload_dir: str = str(BASE_DIR / "uploads")
    faiss_index_dir: str = str(BASE_DIR / "faiss_indexes")
    max_file_size_mb: int = 50
    max_extract_chars: int = 250_000

    @property
    def local_models_list(self) -> list[str]:
        return _split_models(self.ollama_local_models)

    @property
    def cloud_models_list(self) -> list[str]:
        return _split_models(self.ollama_cloud_models)


def _split_models(value: str) -> list[str]:
    seen = set()
    models: list[str] = []
    for item in value.split(","):
        model = item.strip()
        if model and model not in seen:
            seen.add(model)
            models.append(model)
    return models


@lru_cache
def get_settings() -> Settings:
    return Settings()
