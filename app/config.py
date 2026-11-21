"""Application configuration and environment settings for SpecMatrix AI."""

from functools import lru_cache
from pathlib import Path
from typing import Optional, List, Dict, Any
import urllib.request
import json
from pydantic_settings import BaseSettings, SettingsConfigDict


def check_ollama_status(base_url: str = "http://localhost:11434", timeout: float = 1.5) -> Dict[str, Any]:
    """Check whether the local Ollama instance is reachable and retrieve available models."""
    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SpecMatrix-AI/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                return {
                    "available": True,
                    "models": models,
                    "error": None
                }
    except Exception as exc:
        return {
            "available": False,
            "models": [],
            "error": str(exc)
        }
    return {
        "available": False,
        "models": [],
        "error": "Bilinmeyen Ollama bağlantı durumu"
    }


def resolve_ollama_model(base_url: str = "http://localhost:11434", preferred_model: str = "llama3.2:3b") -> Optional[str]:
    """Find the best matching Ollama model from available local models, ignoring embedding models for chat."""
    status = check_ollama_status(base_url=base_url)
    if not status["available"] or not status["models"]:
        return None

    models: List[str] = status["models"]
    # Filter out embedding models for LLM chat/auditing
    chat_models = [m for m in models if "embed" not in m.lower()]
    candidates = chat_models if chat_models else models

    # 1. Exact match in chat candidates
    if preferred_model in candidates:
        return preferred_model

    # 2. Exact match in all models
    if preferred_model in models:
        return preferred_model

    # 3. Prefix / tag match on chat models (e.g. 'llama3.2' -> 'llama3.2:3b' or 'llama3.2:latest')
    for m in candidates:
        if m.startswith(preferred_model) or m.split(":")[0] == preferred_model.split(":")[0]:
            return m

    # 4. Any chat model with 'llama' in name
    for m in candidates:
        if "llama" in m.lower():
            return m

    # 5. First chat model
    if chat_models:
        return chat_models[0]

    return models[0] if models else None


class Settings(BaseSettings):
    """Configuration settings loaded from environment variables and/or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # LLM Provider Selection: 'ollama', 'openai', or 'mock'
    LLM_PROVIDER: str = "ollama"

    # Ollama Settings
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text:latest"
    OLLAMA_TIMEOUT: float = 120.0

    # OpenAI Settings
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Vector Store Embedding Provider: 'deterministic' (fast and offline-safe), 'ollama', or 'openai'
    EMBEDDING_PROVIDER: str = "deterministic"

    # Application Settings
    APP_ENV: str = "development"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True

    # RAG & Chunking Settings
    CHUNK_SIZE: int = 650
    CHUNK_OVERLAP: int = 100
    HYBRID_VECTOR_WEIGHT: float = 0.5
    HYBRID_BM25_WEIGHT: float = 0.5
    TOP_K_CHUNKS: int = 3

    # Base Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    SAMPLE_DOCS_DIR: Path = DATA_DIR / "sample_docs"
    SAMPLE_SPECS_DIR: Path = DATA_DIR / "sample_specs"
    VECTOR_STORE_DIR: Path = DATA_DIR / "vector_store"
    STATIC_DIR: Path = BASE_DIR / "app" / "static"

    @property
    def has_openai_key(self) -> bool:
        """Check whether a non-empty OpenAI API key is provided."""
        return bool(self.OPENAI_API_KEY and self.OPENAI_API_KEY.strip())

    @property
    def is_ollama_active(self) -> bool:
        """Check whether Ollama is selected as the primary LLM provider."""
        return self.LLM_PROVIDER.lower().strip() == "ollama"


@lru_cache()
def get_settings() -> Settings:
    """Retrieve and cache the global application settings instance."""
    return Settings()

