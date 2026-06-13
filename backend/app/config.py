from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Local AI Chat"
    APP_VERSION: str = "2.0.0"
    API_PREFIX: str = "/api/v1"

    # ── LLM (OpenAI-compatible; default: LM Studio) ───────────────────────────
    LLM_BASE_URL: str = "http://localhost:1234/v1"
    LLM_API_KEY: str = "lm-studio"
    LLM_MODEL: str = "local-model"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2048
    LLM_TIMEOUT_SECONDS: float = 60.0

    # Vision model for image-context extraction (can reuse LLM_MODEL)
    VISION_LLM_MODEL: str = "local-model"

    # ── Embeddings (OpenAI-compatible; defaults to LM Studio embedding model) ────
    # Uses same provider as LLM; set to Ollama if preferred (http://localhost:11434/v1)
    EMBED_BASE_URL: str = "http://localhost:1234/v1"
    EMBED_API_KEY: str = "lm-studio"
    EMBED_MODEL: str = "text-embedding-qwen3-embedding-0.6b"
    EMBED_TIMEOUT_SECONDS: float = 120.0

    # ── Auth ──────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "change-me"
    JWT_EXPIRE_MINUTES: int = 60

    # ── Google OAuth (optional) ───────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"
    FRONTEND_URL: str = "http://localhost:5173"

    # ── Data stores ───────────────────────────────────────────────────────────
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "chatbot"
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── RAG / Knowledge base ──────────────────────────────────────────────────
    RAG_CHUNK_SIZE: int = 360
    RAG_CHUNK_OVERLAP: int = 0
    AGENTIC_CHUNK_MODEL: str = "local-model"
    AGENTIC_CHUNK_WINDOW_SIZE: int = 5
    AGENTIC_CHUNK_TARGET_CHARS: int = 360
    AGENTIC_CHUNK_MAX_CHARS: int = 1800
    AGENTIC_CHUNK_TIMEOUT_SECONDS: float = 300.0
    MAX_DOCUMENT_BYTES: int = 50 * 1024 * 1024
    VECTOR_STORE_NAME: str = ".vector_store"
    KNOWLEDGE_BASE_DIR: str = "knowledge_base"

    # ── Observability ─────────────────────────────────────────────────────────
    OTEL_ENABLED: bool = False
    OTEL_SERVICE_NAME: str = "chatbot-api"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
