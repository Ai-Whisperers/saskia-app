"""app/rms/api/contracts.py — Standardized API contracts.

Phase 3: API contracts and performance optimizations.

This module provides standardized response formats and contracts
to ensure consistency across all API endpoints.
"""

from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field
from datetime import datetime


T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Standard API response format."""
    
    success: bool = True
    data: Optional[T] = None
    message: str = "Operation successful"
    timestamp: datetime = Field(default_factory=datetime.now)
    request_id: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class APIError(BaseModel):
    """Standard API error format."""
    
    success: bool = False
    error: str
    message: str
    code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    request_id: Optional[str] = None
    details: Optional[dict] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response format."""
    
    success: bool = True
    data: List[T]
    pagination: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    request_id: Optional[str] = None
    
    @classmethod
    def create(
        cls,
        data: List[T],
        page: int = 1,
        per_page: int = 10,
        total: Optional[int] = None
    ) -> "PaginatedResponse[T]":
        """Create a paginated response with metadata."""
        
        if total is None:
            total = len(data)
        
        pagination = {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
            "has_next": page < (total + per_page - 1) // per_page,
            "has_prev": page > 1,
        }
        
        return cls(
            data=data,
            pagination=pagination,
        )


# Common error types
class ErrorCode:
    """Common error codes for API responses."""
    
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    DUPLICATE = "DUPLICATE"
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"


def create_error(
    error: str,
    message: str,
    code: str = ErrorCode.INTERNAL_ERROR,
    details: Optional[dict] = None,
    request_id: Optional[str] = None
) -> APIError:
    """Create a standardized API error response."""
    
    return APIError(
        error=error,
        message=message,
        code=code,
        details=details,
        request_id=request_id,
    )


def create_response(
    data: Any = None,
    message: str = "Operation successful",
    request_id: Optional[str] = None
) -> APIResponse:
    """Create a standardized API response."""
    
    return APIResponse(
        data=data,
        message=message,
        request_id=request_id,
    )