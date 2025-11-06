#!/usr/bin/env python3
"""
Shared Authentication & Logging Utilities for All Microservices

This module provides:
1. JWT token validation
2. User authentication dependencies
3. Role-based authorization
4. Comprehensive logging with request tracking
5. Error handling

Usage:
    from shared.auth_utils import get_current_user, require_admin, setup_logging, log_request

    logger = setup_logging("my-service")

    @app.get("/api/v1/resource")
    async def get_resource(
        user: User = Depends(get_current_user),
        request: Request = None
    ):
        log_request(logger, request, user.id, "GET /api/v1/resource")
        ...
"""

import os
import json
import traceback
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from enum import Enum

from fastapi import Header, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from loguru import logger as loguru_logger
from pydantic import BaseModel
import sys


# ============================================================================
# CONFIGURATION
# ============================================================================

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production-minimum-32-characters-required")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

security = HTTPBearer(auto_error=False)


# ============================================================================
# MODELS
# ============================================================================

class UserRole(str, Enum):
    """User roles for authorization"""
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    L3 = "L3"
    L2 = "L2"
    L1 = "L1"
    USER = "user"


class User(BaseModel):
    """User model from JWT token"""
    id: int
    username: str
    email: Optional[str] = None
    role: str = "user"
    active: bool = True

    class Config:
        use_enum_values = True


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(service_name: str, log_level: str = "INFO"):
    """
    Setup comprehensive logging for a microservice

    Args:
        service_name: Name of the service (e.g., "ticket-service")
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Configured logger instance
    """
    # Remove default logger
    loguru_logger.remove()

    # Add console logger with custom format
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        f"<cyan>{service_name}</cyan> | "
        "<blue>{extra[request_id]}</blue> | "
        "<yellow>{extra[user_id]}</yellow> | "
        "<level>{message}</level>"
    )

    loguru_logger.add(
        sys.stdout,
        format=log_format,
        level=log_level,
        colorize=True,
        backtrace=True,
        diagnose=True
    )

    # Add file logger for errors
    loguru_logger.add(
        f"/var/log/{service_name}/error.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        level="ERROR",
        rotation="100 MB",
        retention="30 days",
        compression="zip",
        catch=True
    )

    # Bind default context
    return loguru_logger.bind(request_id="STARTUP", user_id="SYSTEM")


def log_request(logger_instance, request: Optional[Request], user_id: Any, message: str, extra: Dict = None):
    """
    Log an HTTP request with context

    Args:
        logger_instance: Logger instance
        request: FastAPI Request object
        user_id: User ID making the request
        message: Log message
        extra: Additional context to log
    """
    request_id = "NONE"
    if request:
        request_id = request.headers.get("X-Request-ID", request.headers.get("X-Correlation-ID", "GENERATED"))

    context = logger_instance.bind(
        request_id=request_id,
        user_id=str(user_id) if user_id else "ANONYMOUS"
    )

    log_data = {
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "request_id": request_id
    }

    if request:
        log_data.update({
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host if request.client else "unknown"
        })

    if extra:
        log_data.update(extra)

    context.info(f"{message} | {json.dumps(log_data)}")


def log_error(logger_instance, request: Optional[Request], user_id: Any, error: Exception, message: str):
    """
    Log an error with full traceback

    Args:
        logger_instance: Logger instance
        request: FastAPI Request object
        user_id: User ID
        error: Exception that occurred
        message: Error message
    """
    request_id = "NONE"
    if request:
        request_id = request.headers.get("X-Request-ID", "NONE")

    context = logger_instance.bind(
        request_id=request_id,
        user_id=str(user_id) if user_id else "ANONYMOUS"
    )

    error_data = {
        "message": message,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "traceback": traceback.format_exc(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    if request:
        error_data.update({
            "method": request.method,
            "path": request.url.path
        })

    context.error(f"❌ {message} | {json.dumps(error_data)}")


# ============================================================================
# JWT VALIDATION
# ============================================================================

def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate JWT token

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM]
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ============================================================================
# AUTHENTICATION DEPENDENCIES
# ============================================================================

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = None,
    authorization: Optional[str] = Header(None)
) -> User:
    """
    Get current authenticated user from JWT token

    Supports two methods:
    1. HTTPBearer security scheme (standard)
    2. Authorization header (for compatibility)

    Args:
        credentials: Bearer token from security scheme
        authorization: Authorization header value

    Returns:
        User object

    Raises:
        HTTPException: If authentication fails
    """
    token = None

    # Try to get token from Bearer scheme
    if credentials:
        token = credentials.credentials
    # Try to get token from Authorization header
    elif authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated - no token provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Decode token
    payload = decode_token(token)

    # Extract user data
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token - no user ID",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create User object
    user = User(
        id=int(user_id),
        username=payload.get("username", f"user_{user_id}"),
        email=payload.get("email"),
        role=payload.get("role", "user"),
        active=payload.get("active", True)
    )

    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = None,
    authorization: Optional[str] = Header(None)
) -> Optional[User]:
    """
    Get current user if authenticated, None otherwise
    For endpoints that can work with or without auth

    Args:
        credentials: Bearer token
        authorization: Authorization header

    Returns:
        User object if authenticated, None otherwise
    """
    try:
        return await get_current_user(credentials, authorization)
    except HTTPException:
        return None


# ============================================================================
# AUTHORIZATION DEPENDENCIES
# ============================================================================

async def require_role(
    allowed_roles: List[str],
    credentials: Optional[HTTPAuthorizationCredentials] = None,
    authorization: Optional[str] = Header(None)
) -> User:
    """
    Require user to have one of the specified roles

    Args:
        allowed_roles: List of allowed role strings
        credentials: Bearer token
        authorization: Authorization header

    Returns:
        User object if authorized

    Raises:
        HTTPException: If user doesn't have required role
    """
    user = await get_current_user(credentials, authorization)

    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Required roles: {allowed_roles}, your role: {user.role}"
        )

    return user


async def require_super_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = None,
    authorization: Optional[str] = Header(None)
) -> User:
    """Require SUPER_ADMIN role"""
    return await require_role([UserRole.SUPER_ADMIN.value], credentials, authorization)


async def require_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = None,
    authorization: Optional[str] = Header(None)
) -> User:
    """Require ADMIN or SUPER_ADMIN role"""
    return await require_role(
        [UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value],
        credentials,
        authorization
    )


async def require_manager(
    credentials: Optional[HTTPAuthorizationCredentials] = None,
    authorization: Optional[str] = Header(None)
) -> User:
    """Require MANAGER, ADMIN, or SUPER_ADMIN role"""
    return await require_role(
        [UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value, UserRole.MANAGER.value],
        credentials,
        authorization
    )


async def require_engineer(
    credentials: Optional[HTTPAuthorizationCredentials] = None,
    authorization: Optional[str] = Header(None)
) -> User:
    """Require any engineer level (L1, L2, L3) or above"""
    return await require_role(
        [
            UserRole.SUPER_ADMIN.value,
            UserRole.ADMIN.value,
            UserRole.MANAGER.value,
            UserRole.L3.value,
            UserRole.L2.value,
            UserRole.L1.value
        ],
        credentials,
        authorization
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def is_admin(user: User) -> bool:
    """Check if user is admin or super admin"""
    return user.role in [UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value]


def is_manager_or_above(user: User) -> bool:
    """Check if user is manager or higher"""
    return user.role in [UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value, UserRole.MANAGER.value]


def can_manage_resource(user: User, resource_owner_id: int) -> bool:
    """Check if user can manage a resource (owns it or is admin)"""
    return user.id == resource_owner_id or is_admin(user)
