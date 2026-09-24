"""app/rms/api/__init__.py — API contract layer.

Phase 3: API contracts and performance optimizations.

This package provides standardized API contracts and response formats
to ensure consistency across all endpoints and improve performance.
"""

from .contracts import APIResponse, APIError, PaginatedResponse
from .performance import query_optimizer, response_caching

__all__ = [
    "APIResponse",
    "APIError", 
    "PaginatedResponse",
    "query_optimizer",
    "response_caching",
]