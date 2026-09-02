from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Settings loaded from environment variables or .env file.
    Follows Pydantic v2 BaseSettings pattern.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Razorpay Test Credentials (NEVER live keys)
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""

    # LLM Provider Configuration
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gemini-2.0-flash"

    # Database Configuration (SQLite default)
    DATABASE_URL: str = "sqlite:///./recovery_agent.db"

    # Simulation / Evaluation Controls
    DEMO_TIME_MULTIPLIER: float = 1.0
    RANDOM_SEED: int = 42

    # App Metadata
    APP_NAME: str = "Razorpay AI Revenue Recovery Agent"
    APP_VERSION: str = "0.1.0"

    # CORS Origins
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()
