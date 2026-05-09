"""
services/model_state.py - runtime model selector
"""
from dataclasses import dataclass
from config import get_settings

settings = get_settings()


@dataclass
class RuntimeModel:
    mode: str
    model: str


state = RuntimeModel(
    mode="cloud" if settings.use_cloud_model else "local",
    model=settings.ollama_cloud_model if settings.use_cloud_model else settings.ollama_local_model,
)


def get_active_base_url() -> str:
    if state.mode == "cloud":
        return settings.ollama_cloud_base_url.rstrip("/")
    return settings.ollama_local_base_url.rstrip("/")


def get_active_model() -> str:
    return state.model


def get_active_mode() -> str:
    return state.mode


def set_active_model(mode: str, model: str) -> RuntimeModel:
    mode = mode.lower().strip()
    model = model.strip()

    if mode not in {"local", "cloud"}:
        raise ValueError("Mode must be local or cloud.")

    if not model:
        raise ValueError("Model name is required.")

    if mode == "local":
        allowed = settings.local_models_list
        if allowed and model not in allowed:
            raise ValueError("Selected local model is not in the available local model list.")

    # For cloud, allow any selected model name.
    # Ollama cloud model availability can change, and /api/tags may return models beyond the fallback .env list.
    state.mode = mode
    state.model = model
    return state
