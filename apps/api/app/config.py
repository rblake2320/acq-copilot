"""Application configuration using Pydantic Settings."""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Acquisition Copilot API"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = Field(default="dev", pattern="^(dev|staging|prod)$")
    LOG_LEVEL: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/acq_copilot",
        description="Async PostgreSQL connection string",
    )

    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string for caching",
    )

    # LLM API Keys
    OPENAI_API_KEY: Optional[str] = Field(default=None, description="OpenAI API key")
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, description="Anthropic API key")
    AZURE_OPENAI_API_KEY: Optional[str] = Field(default=None, description="Azure OpenAI API key")
    AZURE_OPENAI_ENDPOINT: Optional[str] = Field(default=None, description="Azure OpenAI endpoint")
    AZURE_OPENAI_DEPLOYMENT: Optional[str] = Field(default=None, description="Azure OpenAI deployment name")

    # External API Endpoints and Keys
    USASPENDING_BASE_URL: str = Field(
        default="https://api.usaspending.gov/api/v2",
        description="USAspending API base URL",
    )
    FEDERAL_REGISTER_BASE_URL: str = Field(
        default="https://www.federalregister.gov/api/v1",
        description="Federal Register API base URL",
    )
    ECFR_BASE_URL: str = Field(
        default="https://www.ecfr.gov/api/versioner/v1",
        description="eCFR API base URL",
    )
    BLS_API_KEY: Optional[str] = Field(default=None, description="Bureau of Labor Statistics API key")
    BLS_BASE_URL: str = Field(
        default="https://api.bls.gov/publicAPI/v2",
        description="BLS API base URL",
    )
    GSA_PERDIEM_BASE_URL: str = Field(
        default="https://api.gsa.gov/travel/perdiem/v3",
        description="GSA Per Diem API base URL",
    )
    GSA_PERDIEM_API_KEY: Optional[str] = Field(default=None, description="GSA Per Diem API key")
    REGULATIONS_GOV_API_KEY: Optional[str] = Field(
        default=None, description="Regulations.gov API key"
    )
    CONGRESS_GOV_API_KEY: Optional[str] = Field(default=None, description="Congress.gov API key")
    CENSUS_API_KEY: Optional[str] = Field(default=None, description="US Census Bureau API key")
    REGULATIONS_GOV_BASE_URL: str = Field(
        default="https://api.regulations.gov/v4",
        description="Regulations.gov API base URL",
    )
    GSA_CALC_BASE_URL: str = Field(
        default="https://www.gsa.gov/",
        description="GSA Contract pricing base URL",
    )

    # Security
    ENCRYPTION_KEY: str = Field(
        default="dev-key-change-in-production",
        description="Encryption key for secrets (use strong key in production)",
    )
    SECRET_KEY: str = Field(
        default="dev-secret-change-in-production",
        description="Secret key for JWT signing",
    )
    ALGORITHM: str = Field(default="HS256", description="JWT algorithm")

    # CORS
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="CORS allowed origins",
    )

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
