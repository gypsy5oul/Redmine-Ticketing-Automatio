"""
Shared database models used across all microservices
This allows services to share the same database initially
"""

# Re-export all models from the monolith
# This maintains compatibility during migration

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Import all models from the original app
# During migration, services will reference these shared models
# Later, each service can have its own models

# This is a placeholder - actual models would be imported from backend/app/models/*
# For now, we maintain backward compatibility
