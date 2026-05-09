"""
services/llm.py - Ollama local and official Ollama cloud client
"""
import json
from typing import AsyncGenerator

import httpx

from config import get_settings
from services.model_state import get_active_base_url, get_active_mode, get_active_model

settings = get_settings()


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if get_active_mode() == "cloud" and settings.ollama_api_key:
        headers["Authorization"] = f"Bearer {settings.ollama_api_key}"
    return headers


def _api_url(path: str) -> str:
    return f"{get_active_base_url()}/api/{path.lstrip('/')}"


def _friendly_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        detail = exc.response.text[:500]
        if exc.response.status_code == 401:
            return "Ollama cloud rejected the API key. Check OLLAMA_API_KEY in .env."
        if exc.response.status_code == 403:
            return "Your Ollama account does not have access to this cloud model. Choose another model."
        if exc.response.status_code == 404:
            return "Model not found. Choose a model from Settings or refresh cloud models."
        return f"Ollama API error {exc.response.status_code}: {detail}"
    return str(exc)


async def list_cloud_models() -> list[str]:
    """Try to load all models available to the user's Ollama cloud API key."""
    if not settings.ollama_api_key:
        return settings.cloud_models_list
    url = f"{settings.ollama_cloud_base_url.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {settings.ollama_api_key}"})
            resp.raise_for_status()
            data = resp.json()
        names = [m.get("name") for m in data.get("models", []) if m.get("name")]
        merged = []
        for name in names + settings.cloud_models_list:
            if name not in merged:
                merged.append(name)
        return merged
    except Exception:
        return settings.cloud_models_list


async def generate(prompt: str, system: str = "", temperature: float = 0.35, max_tokens: int = 1024) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": get_active_model(),
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }

    try:
        async with httpx.AsyncClient(timeout=240.0) as client:
            resp = await client.post(_api_url("chat"), json=payload, headers=_headers())
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "").strip()
    except Exception as e:
        raise RuntimeError(_friendly_error(e)) from e


async def stream_generate(prompt: str, system: str = "", temperature: float = 0.35, max_tokens: int = 1024) -> AsyncGenerator[str, None]:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": get_active_model(),
        "messages": messages,
        "stream": True,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }

    try:
        async with httpx.AsyncClient(timeout=240.0) as client:
            async with client.stream("POST", _api_url("chat"), json=payload, headers=_headers()) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.strip():
                        try:
                            chunk = json.loads(line)
                            token = chunk.get("message", {}).get("content", "")
                            if token:
                                yield token
                            if chunk.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
    except Exception as e:
        yield f"Error: {_friendly_error(e)}"


async def check_connection() -> dict:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(_api_url("tags"), headers=_headers())
            resp.raise_for_status()
            data = resp.json()
            models = [m.get("name") for m in data.get("models", []) if m.get("name")]
            return {"status": "ok", "models": models, "base_url": get_active_base_url(), "mode": get_active_mode()}
    except Exception as e:
        return {"status": "error", "detail": _friendly_error(e), "base_url": get_active_base_url(), "mode": get_active_mode()}
