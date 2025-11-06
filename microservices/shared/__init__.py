"""Shared utilities for all microservices"""
from .auth_utils import (
    setup_logging,
    log_request,
    log_error,
    get_current_user,
    get_current_user_optional,
    require_admin,
    require_manager,
    require_super_admin,
    require_engineer,
    is_admin,
    is_manager_or_above,
    can_manage_resource,
    User,
    UserRole
)

__all__ = [
    "setup_logging",
    "log_request",
    "log_error",
    "get_current_user",
    "get_current_user_optional",
    "require_admin",
    "require_manager",
    "require_super_admin",
    "require_engineer",
    "is_admin",
    "is_manager_or_above",
    "can_manage_resource",
    "User",
    "UserRole"
]
