#!/usr/bin/env python3
"""
Standalone Scheduler Runner
Runs only the background scheduler without the API server
"""

import asyncio
import signal
import sys
from pathlib import Path
from loguru import logger

from app.core.config import settings
from app.core.database import init_db_sync, close_db_sync

# Configure logging
logger.add(
    settings.LOG_FILE,
    rotation="500 MB",
    retention="10 days",
    level=settings.LOG_LEVEL
)


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"📡 Received signal {signum}, shutting down scheduler...")

    # Remove health check file
    health_file = Path("/tmp/scheduler.running")
    if health_file.exists():
        health_file.unlink()

    from app.scheduler.scheduler import stop_scheduler
    stop_scheduler()
    close_db_sync()
    logger.info("✅ Scheduler shutdown complete")
    sys.exit(0)


def main():
    """Main entry point for scheduler"""
    logger.info("=" * 80)
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION} - SCHEDULER ONLY")
    logger.info("=" * 80)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Initialize database
        logger.info("📊 Initializing database connection...")
        init_db_sync()

        # Start scheduler
        logger.info("📅 Starting background scheduler...")
        from app.scheduler.scheduler import start_scheduler
        start_scheduler()

        # Create health check file
        health_file = Path("/tmp/scheduler.running")
        health_file.touch()
        logger.info("💚 Health check file created at /tmp/scheduler.running")

        logger.info("✅ Scheduler started successfully")
        logger.info("=" * 80)
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 80)

        # Keep the scheduler running
        try:
            while True:
                asyncio.get_event_loop().run_until_complete(asyncio.sleep(1))
        except KeyboardInterrupt:
            logger.info("⌨️ Keyboard interrupt received")

    except Exception as e:
        logger.error(f"💥 Failed to start scheduler: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        logger.info("🧹 Cleaning up...")

        # Remove health check file
        health_file = Path("/tmp/scheduler.running")
        if health_file.exists():
            health_file.unlink()

        from app.scheduler.scheduler import stop_scheduler
        stop_scheduler()
        close_db_sync()


if __name__ == "__main__":
    main()
