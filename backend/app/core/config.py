#!/usr/bin/env python3
"""
Enterprise Configuration Management
"""

from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator
import os


class Settings(BaseSettings):
    """Application settings with validation"""

    # Application
    APP_NAME: str = "DevOps Ticket Management System"
    APP_VERSION: str = "3.0.0"
    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    SECRET_KEY: str = Field(..., min_length=32)

    # Database
    DATABASE_URL: str = Field(..., description="PostgreSQL connection URL")
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: Optional[str] = None
    REDIS_MAX_CONNECTIONS: int = 50

    # Redmine
    REDMINE_BASE_URL: str
    REDMINE_API_KEY: str
    DEVOPS_PROJECT_ID: int = 1
    DEVOPS_TEAM_GROUP_ID: int = 6

    # LLM
    LLM_BASE_URL: str
    LLM_MODEL: str
    LLM_TIMEOUT: int = 120
    LLM_MAX_TOKENS: int = 2000
    LLM_TEMPERATURE: float = 0.7

    # Notifications
    GOOGLE_CHAT_WEBHOOK: Optional[str] = None
    GOOGLE_CHAT_ENABLED: bool = True
    SLACK_WEBHOOK: Optional[str] = None
    SLACK_ENABLED: bool = False

    # Scheduler
    ENABLE_SCHEDULER: bool = True  # Set to False to disable scheduler (for API workers)
    TICKET_PROCESSING_INTERVAL: int = 2  # minutes
    SLA_CHECK_INTERVAL: int = 1  # minutes
    ANALYTICS_UPDATE_INTERVAL: int = 60  # minutes
    REDMINE_STATUS_SYNC_INTERVAL: int = 5  # minutes

    # ML Models
    ML_MODELS_PATH: str = "./models"
    ML_TRAINING_ENABLED: bool = True
    ML_MIN_TRAINING_SAMPLES: int = 50

    # JWT
    JWT_SECRET_KEY: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    CORS_ALLOW_CREDENTIALS: bool = True

    # Monitoring
    PROMETHEUS_ENABLED: bool = True
    SENTRY_DSN: Optional[str] = None

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"

    # Public base URL for external callbacks (Chat rotation links)
    PUBLIC_API_BASE_URL: Optional[str] = None

    # Business hours configuration (used for off-hours routing logic)
    BUSINESS_TIMEZONE: str = "Asia/Kolkata"  # Changed from UTC to match team timezone
    BUSINESS_HOURS_START: int = 9   # 9 AM local time
    BUSINESS_HOURS_END: int = 18    # 6 PM local time
    BUSINESS_DAYS: List[int] = [0, 1, 2, 3, 4]  # Monday-Friday

    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
