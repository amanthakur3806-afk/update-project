"""
Configuration Module
Loads environment variables from .env file (if present) and exposes them
as a single `settings` singleton used across the entire application.

No hardcoded secrets — all values come from the environment or safe defaults.
"""
import os
from pathlib import Path

# Load .env file automatically (does NOT override variables already set in OS environment)
try:
    from dotenv import load_dotenv
    _env_file = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=_env_file, override=False)
except ImportError:
    pass  # python-dotenv not installed — rely on OS environment variables

from pydantic import BaseModel

# Absolute path to the project root directory
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseModel):
    """
    Central configuration model.
    All values are read from environment variables (or .env file).
    Every field has a safe default so the app works out of the box.
    """

    BASE_DIR: Path = BASE_DIR

    # --- Server ---
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8080"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

    # --- Database ---
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR}/agent_platform.db"
    )

    # --- Mode ---
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "True").lower() in ("true", "1", "yes")

    # --- LLM Providers ---
    # Groq (ultra-fast inference) or OpenAI
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip()

    # OpenAI (optional)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_EMBEDDING_MODEL: str = os.getenv(
        "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
    )

    # --- Storage Paths ---
    VECTOR_STORE_DIR: Path = BASE_DIR / os.getenv("VECTOR_STORE_DIR", "vector_store").lstrip("./")
    KNOWLEDGE_BASE_DIR: Path = BASE_DIR / os.getenv("KNOWLEDGE_BASE_DIR", "knowledge").lstrip("./")
    LOGS_DIR: Path = BASE_DIR / os.getenv("LOGS_DIR", "logs").lstrip("./")
    EXECUTIONS_LOG_DIR: Path = BASE_DIR / os.getenv("LOGS_DIR", "logs").lstrip("./") / "executions"

    model_config = {"arbitrary_types_allowed": True}


settings = Settings()

# Create required directories on startup so no code has to handle missing folders
settings.VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
settings.KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)
settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
settings.EXECUTIONS_LOG_DIR.mkdir(parents=True, exist_ok=True)
