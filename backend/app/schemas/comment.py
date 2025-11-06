#!/usr/bin/env python3
"""
Pydantic schemas for ticket comments
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class CommentType(str, Enum):
    """Comment visibility types"""
    PUBLIC = "public"
    INTERNAL = "internal"


class CommentCreate(BaseModel):
    """Schema for creating a new comment"""
    content: str = Field(..., min_length=1, max_length=10000, description="Comment content")
    comment_type: CommentType = Field(default=CommentType.PUBLIC, description="Comment visibility")


class CommentUpdate(BaseModel):
    """Schema for updating an existing comment"""
    content: str = Field(..., min_length=1, max_length=10000, description="Updated comment content")


class CommentResponse(BaseModel):
    """Schema for comment response"""
    id: int
    ticket_id: int
    author_id: Optional[int]
    author_name: Optional[str] = None
    content: str
    comment_type: str
    created_at: datetime
    updated_at: Optional[datetime]
    edited: bool
    has_attachments: bool
    attachment_count: int

    class Config:
        from_attributes = True


class CommentListResponse(BaseModel):
    """Schema for list of comments"""
    comments: list[CommentResponse]
    total: int
    ticket_id: int
