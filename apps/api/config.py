"""Application configuration and settings."""
import os

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(extra="ignore", env_file=".env")

    DATA_MODE: str = os.getenv("DATA_MODE", "demo")
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "./data/memory.db")
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))


settings = Settings()
