from functools import lru_cache
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Settings Contract.
    Validates and parses environment variables at boot time.
    Fails fast if mandatory secrets are missing or invalid.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Groq API Configuration
    GROQ_API_KEY: str = Field(
        ...,
        description="Groq Cloud API Key (must begin with 'gsk_')"
    )
    INFERENCE_MODEL: str = Field(
        default="openai/gpt-oss-20b",
        description="Target LLM model identifier on Groq"
    )
    
    # Qdrant Vector DB Configuration
    QDRANT_HOST: str = Field(default="127.0.0.1")
    QDRANT_PORT: int = Field(default=6333)
    QDRANT_GRPC_PORT: int = Field(default=6334)
    QDRANT_COLLECTION_NAME: str = Field(default="engineering_blueprints")

    # Application State
    ENVIRONMENT: Literal["development", "production", "test"] = Field(
        default="development"
    )
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO"
    )

    @field_validator("GROQ_API_KEY")
    @classmethod
    def validate_groq_api_key(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("GROQ_API_KEY cannot be an empty string.")
        if cleaned == "gsk_your_actual_groq_api_key_here":
            raise ValueError(
                "Default template key detected in .env! "
                "You must replace it with your real Groq API key from console.groq.com."
            )
        if not cleaned.startswith("gsk_"):
            raise ValueError(
                "Invalid GROQ_API_KEY format. Groq API keys must begin with 'gsk_'."
            )
        return cleaned


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached, validated singleton instance of application settings.
    Guarantees that .env is read from disk exactly once.
    """
    return Settings()

# Export instantiated singleton for standard service imports
settings: Settings = get_settings()