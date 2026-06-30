"""
PressureLab AI - Configuration
Environment-based configuration using pydantic-settings.
"""

from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path


ENV_FILE = Path(__file__).resolve().with_name(".env")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "PressureLab AI"
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # LLM Provider Selection: "huggingface" or "watsonx"
    llm_provider: str = "huggingface"

    # IBM Granite (Hugging Face)
    hf_api_key: str = ""
    granite_model_id: str = "ibm-granite/granite-3.3-8b-instruct"

    # IBM watsonx.ai (optional alternative)
    watsonx_api_key: Optional[str] = None
    watsonx_project_id: Optional[str] = None
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"

    # Database
    database_url: str = "postgresql://pressurelab:pressurelab@localhost:5432/pressurelab"
    database_fallback_url: str = "sqlite:///./pressurelab.db"

    # Redis
    redis_url: Optional[str] = None

    # Langflow
    langflow_url: str = "http://localhost:7860"
    langflow_api_key: Optional[str] = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def effective_database_url(self) -> str:
        """Use PostgreSQL if available, fall back to SQLite."""
        if self.database_url and "postgresql" not in self.database_url:
            return self.database_url
        if self.database_url and "postgresql" in self.database_url:
            return self.database_url
        return self.database_fallback_url

    class Config:
        env_file = str(ENV_FILE)
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
