#!/usr/bin/env python3
"""
Auth Service - Complete Standalone Microservice
Port: 8001
Purpose: Authentication, Authorization, User Management

This service is completely independent with all code duplicated.
"""

from fastapi import FastAPI, Depends, HTTPException, status, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLEnum, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, timedelta, timezone
from typing import Optional, Generator
from pydantic import BaseModel, EmailStr, Field
from pydantic_settings import BaseSettings
from passlib.context import CryptContext
from jose import JWTError, jwt
import enum
import os
import sys

# Add shared module for logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from shared.auth_utils import setup_logging, log_request

# ============================================================================
# Configuration (Duplicated from app/core/config.py)
# ============================================================================

class Settings(BaseSettings):
    # Service
    SERVICE_PORT: int = 8001

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://devops_user:devops_password@postgres:5432/devops_tickets")

    # JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: list = ["http://localhost:3000", "http://10.0.2.121:3000"]

    class Config:
        case_sensitive = True

settings = Settings()


# ============================================================================
# Database (Duplicated from app/core/database.py)
# ============================================================================

Base = declarative_base()

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# Models (Duplicated from app/models/user.py)
# ============================================================================

class UserRole(str, enum.Enum):
    """User roles"""
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    VIEWER = "viewer"


class User(Base):
    """User model"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(200), unique=True, nullable=False, index=True)
    hashed_password = Column(String(200), nullable=False)
    full_name = Column(String(200))

    role = Column(SQLEnum(UserRole), default=UserRole.VIEWER, nullable=False)
    active = Column(Boolean, default=True, index=True)

    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String(200))

    last_login = Column(DateTime(timezone=True))
    last_activity = Column(DateTime(timezone=True))
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True))
    force_password_change = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True))
    created_by = Column(String(200))

    @property
    def is_locked(self) -> bool:
        """Check if account is locked"""
        if self.locked_until:
            return datetime.now(timezone.utc) < self.locked_until
        return False


# ============================================================================
# Security Utilities (Duplicated from app/core/security.py)
# ============================================================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash password"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})

    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc), "type": "refresh"})

    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> dict:
    """Decode JWT token"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError as e:
        raise JWTError(f"Could not validate token: {str(e)}")


# ============================================================================
# User Service (Duplicated from app/services/user_service.py)
# ============================================================================

class UserService:
    """User service"""

    def __init__(self, db: Session):
        self.db = db

    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authenticate user"""
        user = self.db.query(User).filter(
            (User.username == username) | (User.email == username)
        ).first()

        if not user:
            return None

        if user.is_locked or not user.active:
            return None

        if not verify_password(password, user.hashed_password):
            self.increment_failed_attempts(user.id)
            return None

        self.reset_failed_attempts(user.id)
        self.update_last_login(user.id)
        return user

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        return self.db.query(User).filter(User.username == username).first()

    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        return self.db.query(User).filter(User.email == email).first()

    def create_user(self, username: str, email: str, password: str, full_name: str,
                    role: UserRole = UserRole.VIEWER, created_by: Optional[str] = None) -> User:
        """Create new user"""
        if self.get_by_username(username):
            raise ValueError(f"Username '{username}' already exists")

        if self.get_by_email(email):
            raise ValueError(f"Email '{email}' already exists")

        user = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            full_name=full_name,
            role=role,
            active=True,
            created_by=created_by,
            created_at=datetime.now(timezone.utc)
        )

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_password(self, user_id: int, new_password: str) -> bool:
        """Update user password"""
        user = self.get_by_id(user_id)
        if not user:
            return False

        user.hashed_password = get_password_hash(new_password)
        user.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return True

    def update_last_login(self, user_id: int):
        """Update last login"""
        user = self.get_by_id(user_id)
        if user:
            user.last_login = datetime.now(timezone.utc)
            self.db.commit()

    def update_last_activity(self, user_id: int):
        """Update last activity"""
        user = self.get_by_id(user_id)
        if user:
            user.last_activity = datetime.now(timezone.utc)
            self.db.commit()

    def increment_failed_attempts(self, user_id: int):
        """Increment failed login attempts"""
        user = self.get_by_id(user_id)
        if not user:
            return

        user.failed_login_attempts += 1

        if user.failed_login_attempts >= 5:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)

        self.db.commit()

    def reset_failed_attempts(self, user_id: int):
        """Reset failed attempts"""
        user = self.get_by_id(user_id)
        if user:
            user.failed_login_attempts = 0
            user.locked_until = None
            self.db.commit()

    def deactivate_user(self, user_id: int) -> bool:
        """Deactivate user"""
        user = self.get_by_id(user_id)
        if not user:
            return False

        user.active = False
        user.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return True

    def activate_user(self, user_id: int) -> bool:
        """Activate user"""
        user = self.get_by_id(user_id)
        if not user:
            return False

        user.active = True
        user.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return True


# ============================================================================
# Dependencies (Duplicated from app/api/deps.py)
# ============================================================================

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = credentials.credentials
        payload = decode_token(token)

        user_id: Optional[int] = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        user_service = UserService(db)
        user = user_service.get_by_id(int(user_id))

        if user is None:
            raise credentials_exception

        if not user.active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")

        if user.is_locked:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Account is locked until {user.locked_until}")

        user_service.update_last_activity(user.id)
        return user

    except JWTError:
        raise credentials_exception

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require admin role"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Required: admin"
        )
    return current_user


# ============================================================================
# Pydantic Schemas
# ============================================================================

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict

class RefreshRequest(BaseModel):
    refresh_token: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)

class ResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8)
    force_change: bool = True

class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str
    role: UserRole = UserRole.VIEWER

class UserResponse(BaseModel):
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
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Auth Service",
    version="1.0.0",
    description="Authentication & User Management Microservice"
)

# Setup enhanced logging
logger = setup_logging("auth-service", os.getenv("LOG_LEVEL", "INFO"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    return {
        "service": "auth-service",
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# Authentication Endpoints
# ============================================================================

@app.post("/api/v1/auth/login", response_model=LoginResponse)
async def login(login_data: LoginRequest, request: Request = None, db: Session = Depends(get_db)):
    """Login with username/password - Public endpoint"""
    log_request(logger, request, None, "POST /api/v1/auth/login")
    user_service = UserService(db)
    user = user_service.authenticate(login_data.username, login_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value},
        expires_delta=access_token_expires
    )

    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    logger.info(f"✅ User '{user.username}' logged in successfully")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
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


@app.post("/api/v1/auth/refresh", response_model=LoginResponse)
async def refresh_token_endpoint(refresh_data: RefreshRequest, request: Request = None, db: Session = Depends(get_db)):
    """Refresh access token - Public endpoint"""
    log_request(logger, request, None, "POST /api/v1/auth/refresh")
    try:
        payload = decode_token(refresh_data.refresh_token)

        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        user_id = int(payload.get("sub"))
        user_service = UserService(db)
        user = user_service.get_by_id(user_id)

        if not user or not user.active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

        access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id), "role": user.role.value},
            expires_delta=access_token_expires
        )

        new_refresh_token = create_refresh_token(data={"sub": str(user.id)})

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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")


@app.get("/api/v1/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user), request: Request = None):
    """Get current user info - Requires: Any authenticated user"""
    log_request(logger, request, current_user.id, "GET /api/v1/auth/me")
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role.value,
        "active": current_user.active,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None
    }


@app.post("/api/v1/auth/logout")
async def logout(current_user: User = Depends(get_current_user), request: Request = None):
    """Logout (client-side token discard) - Requires: Any authenticated user"""
    log_request(logger, request, current_user.id, "POST /api/v1/auth/logout")
    logger.info(f"✅ User '{current_user.username}' logged out")
    return {
        "message": "Logged out successfully",
        "detail": "Please discard your access and refresh tokens"
    }


@app.post("/api/v1/auth/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Change password - Requires: Any authenticated user"""
    log_request(logger, request, current_user.id, "POST /api/v1/auth/change-password")
    user_service = UserService(db)

    authenticated_user = user_service.authenticate(current_user.username, password_data.old_password)
    if not authenticated_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")

    success = user_service.update_password(current_user.id, password_data.new_password)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update password")

    current_user.force_password_change = False
    db.commit()

    logger.info(f"✅ Password changed for user '{current_user.username}'")
    return {"message": "Password changed successfully"}


# ============================================================================
# Admin User Management
# ============================================================================

@app.post("/api/v1/auth/users", response_model=UserResponse)
async def create_user(
    user_data: CreateUserRequest,
    current_user: User = Depends(require_admin),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Create new user (admin only) - Requires: Admin or Super Admin role"""
    log_request(logger, request, current_user.id, "POST /api/v1/auth/users")
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.get("/api/v1/auth/users")
async def list_users(
    current_user: User = Depends(require_admin),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """List all users (admin only) - Requires: Admin or Super Admin role"""
    log_request(logger, request, current_user.id, "GET /api/v1/auth/users")
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


@app.put("/api/v1/auth/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Deactivate user (admin only) - Requires: Admin or Super Admin role"""
    log_request(logger, request, current_user.id, f"PUT /api/v1/auth/users/{user_id}/deactivate")
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate your own account")

    user_service = UserService(db)
    success = user_service.deactivate_user(user_id)

    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return {"message": "User deactivated successfully"}


@app.put("/api/v1/auth/users/{user_id}/activate")
async def activate_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Activate user (admin only) - Requires: Admin or Super Admin role"""
    log_request(logger, request, current_user.id, f"PUT /api/v1/auth/users/{user_id}/activate")
    user_service = UserService(db)
    success = user_service.activate_user(user_id)

    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return {"message": "User activated successfully"}


@app.post("/api/v1/auth/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    password_data: ResetPasswordRequest,
    current_user: User = Depends(require_admin),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Reset user password (admin only) - Requires: Admin or Super Admin role"""
    log_request(logger, request, current_user.id, f"POST /api/v1/auth/users/{user_id}/reset-password")
    user_service = UserService(db)
    target_user = user_service.get_by_id(user_id)

    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    success = user_service.update_password(user_id, password_data.new_password)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to reset password")

    if password_data.force_change:
        target_user.force_password_change = True
        db.commit()

    logger.info(f"✅ Admin '{current_user.username}' reset password for user '{target_user.username}'")

    return {
        "message": "Password reset successfully",
        "detail": f"Password reset for user '{target_user.username}'" +
                 (" - user will be prompted to change password on next login" if password_data.force_change else "")
    }


# ============================================================================
# Startup
# ============================================================================

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Starting Auth Service v1.0.0")
    logger.info(f"✅ Auth Service started successfully on port {settings.SERVICE_PORT}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("👋 Shutting down Auth Service...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.SERVICE_PORT)
