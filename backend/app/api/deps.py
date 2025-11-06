#!/usr/bin/env python3
"""
API Dependencies - Reusable dependencies for FastAPI routes
"""

from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User, UserRole
from app.services.user_service import UserService

# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token

    Args:
        credentials: HTTP Bearer token from Authorization header
        db: Database session

    Returns:
        Current authenticated User object

    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode JWT token
        token = credentials.credentials
        payload = decode_token(token)

        # Get user_id from token
        user_id: Optional[int] = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        # Get user from database
        user_service = UserService(db)
        user = user_service.get_by_id(int(user_id))

        if user is None:
            raise credentials_exception

        # Check if user is active
        if not user.active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )

        # Check if user is locked
        if user.is_locked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account is locked until {user.locked_until}"
            )

        # Update last activity
        user_service.update_last_activity(user.id)

        return user

    except JWTError:
        raise credentials_exception


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current active user (alias for get_current_user)

    Args:
        current_user: Current user from get_current_user

    Returns:
        Current active User object
    """
    return current_user


async def require_role(
    allowed_roles: list[UserRole],
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require user to have one of the specified roles

    Args:
        allowed_roles: List of allowed roles
        current_user: Current authenticated user

    Returns:
        Current user if role matches

    Raises:
        HTTPException: If user doesn't have required role
    """
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Required roles: {[r.value for r in allowed_roles]}"
        )
    return current_user


async def require_super_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """Require SUPER_ADMIN role"""
    return await require_role([UserRole.SUPER_ADMIN], current_user)


async def require_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """Require ADMIN or SUPER_ADMIN role"""
    return await require_role([UserRole.SUPER_ADMIN, UserRole.ADMIN], current_user)


async def require_manager(
    current_user: User = Depends(get_current_user)
) -> User:
    """Require MANAGER, ADMIN, or SUPER_ADMIN role"""
    return await require_role(
        [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER],
        current_user
    )


# Optional authentication (for public endpoints that can show more data if authenticated)
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get current user if token provided, None otherwise

    Args:
        credentials: Optional HTTP Bearer token
        db: Database session

    Returns:
        User object if authenticated, None if not
    """
    if not credentials:
        return None

    try:
        token = credentials.credentials
        payload = decode_token(token)
        user_id: Optional[int] = payload.get("sub")

        if user_id is None:
            return None

        user_service = UserService(db)
        user = user_service.get_by_id(int(user_id))

        if user and user.active and not user.is_locked:
            user_service.update_last_activity(user.id)
            return user

        return None

    except JWTError:
        return None
