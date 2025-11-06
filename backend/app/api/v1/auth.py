#!/usr/bin/env python3
"""
Authentication Router - Login, logout, token management
"""

from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from loguru import logger

from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.core.config import settings
from app.models.user import User, UserRole
from app.services.user_service import UserService
from app.api.deps import get_current_user, require_admin

router = APIRouter()
security = HTTPBearer()


# ============================================================================
# Pydantic Schemas
# ============================================================================

class LoginRequest(BaseModel):
    """Login request schema"""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")


class LoginResponse(BaseModel):
    """Login response schema"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: dict


class RefreshRequest(BaseModel):
    """Token refresh request"""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Change password request"""
    old_password: str
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")


class ResetPasswordRequest(BaseModel):
    """Admin reset password request"""
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")
    force_change: bool = Field(default=True, description="Force user to change password on next login")


class CreateUserRequest(BaseModel):
    """Create user request (admin only)"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str
    role: UserRole = UserRole.VIEWER


class UserResponse(BaseModel):
    """User response schema"""
    id: int
    username: str
    email: str
    full_name: Optional[str]
    role: str
    active: bool
    created_at: str

    class Config:
        from_attributes = True


# ============================================================================
# Authentication Endpoints
# ============================================================================

@router.post("/login", response_model=LoginResponse, tags=["Authentication"])
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login with username/email and password

    Returns JWT access token and refresh token
    """
    user_service = UserService(db)

    # Authenticate user
    user = user_service.authenticate(login_data.username, login_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value},
        expires_delta=access_token_expires
    )

    # Create refresh token
    refresh_token = create_refresh_token(
        data={"sub": str(user.id)}
    )

    logger.info(f"✅ User '{user.username}' logged in successfully")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # in seconds
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "active": user.active,
            "force_password_change": user.force_password_change
        }
    }


@router.post("/refresh", response_model=LoginResponse, tags=["Authentication"])
async def refresh_token(
    refresh_data: RefreshRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token
    """
    try:
        # Decode refresh token
        payload = decode_token(refresh_data.refresh_token)

        # Check if it's a refresh token
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        # Get user
        user_id = int(payload.get("sub"))
        user_service = UserService(db)
        user = user_service.get_by_id(user_id)

        if not user or not user.active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )

        # Create new access token
        access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id), "role": user.role.value},
            expires_delta=access_token_expires
        )

        # Create new refresh token
        new_refresh_token = create_refresh_token(
            data={"sub": str(user.id)}
        )

        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value,
                "active": user.active
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.get("/me", response_model=UserResponse, tags=["Authentication"])
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user information
    """
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role.value,
        "active": current_user.active,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None
    }


@router.post("/logout", tags=["Authentication"])
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout (client should discard tokens)

    Note: JWT tokens are stateless, so actual invalidation happens on client side.
    For production, consider implementing a token blacklist in Redis.
    """
    logger.info(f"✅ User '{current_user.username}' logged out")

    return {
        "message": "Logged out successfully",
        "detail": "Please discard your access and refresh tokens"
    }


@router.post("/change-password", tags=["Authentication"])
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change current user's password
    """
    user_service = UserService(db)

    # Verify old password
    authenticated_user = user_service.authenticate(current_user.username, password_data.old_password)

    if not authenticated_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )

    # Update password
    success = user_service.update_password(current_user.id, password_data.new_password)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password"
        )

    # Clear force_password_change flag
    current_user.force_password_change = False
    db.commit()

    logger.info(f"✅ Password changed for user '{current_user.username}'")

    return {
        "message": "Password changed successfully",
        "detail": "Please login again with your new password"
    }


# ============================================================================
# Admin User Management
# ============================================================================

@router.post("/users", response_model=UserResponse, tags=["User Management"])
async def create_user(
    user_data: CreateUserRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new user (admin only)
    """
    user_service = UserService(db)

    try:
        new_user = user_service.create_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name,
            role=user_data.role,
            created_by=current_user.username
        )

        return {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "full_name": new_user.full_name,
            "role": new_user.role.value,
            "active": new_user.active,
            "created_at": new_user.created_at.isoformat()
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/users", tags=["User Management"])
async def list_users(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    List all users (admin only)
    """
    users = db.query(User).all()

    return {
        "users": [
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value,
                "active": user.active,
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "created_at": user.created_at.isoformat() if user.created_at else None
            }
            for user in users
        ]
    }


@router.put("/users/{user_id}/deactivate", tags=["User Management"])
async def deactivate_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Deactivate a user (admin only)
    """
    user_service = UserService(db)

    # Prevent self-deactivation
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )

    success = user_service.deactivate_user(user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return {"message": "User deactivated successfully"}


@router.put("/users/{user_id}/activate", tags=["User Management"])
async def activate_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Activate a user (admin only)
    """
    user_service = UserService(db)

    success = user_service.activate_user(user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return {"message": "User activated successfully"}


@router.post("/users/{user_id}/reset-password", tags=["User Management"])
async def reset_user_password(
    user_id: int,
    password_data: ResetPasswordRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Reset a user's password (admin only)

    This endpoint allows administrators to reset any user's password.
    Optionally forces the user to change their password on next login.
    """
    user_service = UserService(db)

    # Get target user
    target_user = user_service.get_by_id(user_id)

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Update password
    success = user_service.update_password(user_id, password_data.new_password)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password"
        )

    # Update force_password_change flag
    if password_data.force_change:
        target_user.force_password_change = True
        db.commit()

    logger.info(f"✅ Admin '{current_user.username}' reset password for user '{target_user.username}'")

    return {
        "message": "Password reset successfully",
        "detail": f"Password reset for user '{target_user.username}'" +
                 (" - user will be prompted to change password on next login" if password_data.force_change else "")
    }
