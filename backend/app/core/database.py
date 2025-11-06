#!/usr/bin/env python3
"""
Database connection management
"""

from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from redis import Redis
from redis.connection import ConnectionPool
from typing import Generator
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# PostgreSQL Setup
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Redis Setup
redis_pool = ConnectionPool.from_url(
    settings.REDIS_URL,
    max_connections=settings.REDIS_MAX_CONNECTIONS,
    decode_responses=True,
)
redis_client = Redis(connection_pool=redis_pool)


def get_db() -> Generator[Session, None, None]:
    """Dependency for getting DB session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_redis() -> Redis:
    """Dependency for getting Redis client"""
    return redis_client


async def init_db():
    """Initialize database tables (async version for FastAPI)"""
    try:
        Base.metadata.create_all(bind=engine)
        _apply_post_schema_migrations()
        logger.info("✅ Database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise


def init_db_sync():
    """Initialize database tables (sync version for standalone scheduler)"""
    try:
        Base.metadata.create_all(bind=engine)
        _apply_post_schema_migrations()
        logger.info("✅ Database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise


async def close_db():
    """Close database connections (async version for FastAPI)"""
    try:
        engine.dispose()
        redis_client.close()
        logger.info("✅ Database connections closed")
    except Exception as e:
        logger.error(f"❌ Error closing database: {e}")


def close_db_sync():
    """Close database connections (sync version for standalone scheduler)"""
    try:
        engine.dispose()
        redis_client.close()
        logger.info("✅ Database connections closed")
    except Exception as e:
        logger.error(f"❌ Error closing database: {e}")


def _apply_post_schema_migrations() -> None:
    """
    Apply lightweight schema adjustments that need to run even if Alembic migrations
    have not yet been executed (e.g., new optional columns).
    """
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE ticket_history "
                    "ADD COLUMN IF NOT EXISTS requester_name VARCHAR(255)"
                )
            )
    except Exception as migration_error:
        logger.error("❌ Failed to apply post-schema migrations: %s", migration_error)
        raise
