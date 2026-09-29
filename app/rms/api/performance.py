"""app/rms/api/performance.py — Performance optimization utilities.

Phase 3: API contracts and performance optimizations.

This module provides performance optimization utilities including
query optimization, response caching, and bulk operation helpers.
"""

import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar

# Type variables for generic functions
T = TypeVar("T")


class QueryOptimizer:
    """Optimize database queries for better performance."""

    @staticmethod
    def batch_operations(
        batch_size: int = 100,
        delay_between_batches: float = 0.1
    ) -> Callable:
        """Decorator for batching database operations."""

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:  # noqa: ANN401 — generic decorator wrapper
                result = []
                items = kwargs.get('items', args[0] if args else [])

                if not isinstance(items, (list, tuple)):
                    return func(*args, **kwargs)

                # Process in batches
                for i in range(0, len(items), batch_size):
                    batch = items[i:i + batch_size]
                    batch_kwargs = kwargs.copy()
                    batch_kwargs['items'] = batch
                    batch_result = func(*args[1:], **batch_kwargs)
                    result.extend(batch_result if isinstance(batch_result, list) else [batch_result])

                    # Small delay between batches to reduce database load
                    if i + batch_size < len(items):
                        time.sleep(delay_between_batches)

                return result
            return wrapper
        return decorator

    @staticmethod
    def select_only_needed_fields(
        model_class: Any,  # noqa: ANN401
        required_fields: List[str]
    ) -> Callable:
        """Decorator to select only required fields from database queries."""

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:  # noqa: ANN401 — generic decorator wrapper
                # Apply field selection to query if it's a query
                query = kwargs.get('query') or (args[0] if args else None)
                if query and hasattr(query, 'options'):
                    # This would require SQLAlchemy specific implementation
                    # For now, just log the optimization opportunity
                    print(f"Optimization opportunity: Select only {required_fields} for {model_class.__name__}")

                return func(*args, **kwargs)
            return wrapper
        return decorator


class ResponseCacher:
    """Simple response caching for frequently accessed data."""

    def __init__(self, ttl: int = 300):
        """Initialize cache with Time-To-Live in seconds."""
        self.cache: Dict[str, Dict] = {}
        self.ttl = ttl

    def get(self, key: str) -> Optional[Any]:  # noqa: ANN401 — cache returns Any
        """Get value from cache if it exists and is not expired."""
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry['timestamp'] < self.ttl:
                return entry['value']
            else:
                del self.cache[key]
        return None

    def set(self, key: str, value: Any) -> None:  # noqa: ANN401
        """Set value in cache with current timestamp."""
        self.cache[key] = {
            'value': value,
            'timestamp': time.time()
        }

    def clear(self) -> None:
        """Clear all cached values."""
        self.cache.clear()


# Global cache instance
response_cache = ResponseCacher(ttl=300)  # 5 minutes


def cache_response(key_prefix: str = "api", ttl: int = 300) -> Callable:
    """Decorator for caching API responses."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:  # noqa: ANN401 — generic cache decorator
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(kwargs))}"

            # Try to get from cache first
            cached_result = response_cache.get(cache_key)
            if cached_result is not None:
                print(f"Cache hit for {func.__name__}")
                return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            response_cache.set(cache_key, result)
            return result
        return wrapper
    return decorator


@contextmanager
def performance_timer(operation_name: str):
    """Context manager for timing operations."""
    start_time = time.time()
    yield
    end_time = time.time()
    duration = end_time - start_time
    print(f"{operation_name} took {duration:.3f} seconds")


def optimize_bulk_operations(items: List[T], operation_func: Callable, batch_size: int = 100) -> List[T]:
    """Optimize bulk operations by processing in batches."""
    results = []

    with performance_timer(f"Bulk operation ({len(items)} items)"):
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_results = operation_func(batch)
            results.extend(batch_results if isinstance(batch_results, list) else [batch_results])

    return results


# Common performance utilities
def measure_query_performance(query_func: Callable) -> Callable:
    """Decorator to measure and log query performance."""

    @wraps(query_func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = query_func(*args, **kwargs)
        end_time = time.time()
        duration = end_time - start_time

        if duration > 1.0:  # Log queries taking longer than 1 second
            print(f"Slow query detected: {query_func.__name__} took {duration:.3f}s")

        return result
    return wrapper
