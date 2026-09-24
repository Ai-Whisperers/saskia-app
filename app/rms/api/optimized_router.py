"""app/rms/api/optimized_router.py — Performance-optimized router.

Phase 3: API contracts and performance optimizations.

Demonstration of how to use the performance optimization utilities
and standardized API contracts for better performance and consistency.
"""

from typing import List, Optional
from fastapi import APIRouter, Query

from app.rms.api.contracts import APIResponse, PaginatedResponse, create_response, create_error
from app.rms.api.performance import QueryOptimizer, response_cache, cache_response

router = APIRouter(prefix="/optimized", tags=["optimized"])


@router.get("/products", response_model=APIResponse[dict])
@cache_response(key_prefix="products", ttl=300)
def get_products_optimized(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None
):
    """Get products with pagination and caching.
    
    This demonstrates:
    1. Standardized API response format
    2. Response caching for performance
    3. Pagination support
    """
    
    # Mock data for demonstration
    all_products = [
        {"id": 1, "name": "Product A", "price_gs": 1000, "stock_qty": 10},
        {"id": 2, "name": "Product B", "price_gs": 2000, "stock_qty": 5},
        {"id": 3, "name": "Product C", "price_gs": 1500, "stock_qty": 8},
        {"id": 4, "name": "Product D", "price_gs": 3000, "stock_qty": 2},
        {"id": 5, "name": "Product E", "price_gs": 2500, "stock_qty": 7},
    ]
    
    # Filter by search if provided
    if search:
        products = [p for p in all_products if search.lower() in p["name"].lower()]
    else:
        products = all_products
    
    # Apply pagination
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_products = products[start_idx:end_idx]
    
    # Create paginated response
    paginated_response = PaginatedResponse.create(
        data=paginated_products,
        page=page,
        per_page=per_page,
        total=len(products)
    )
    
    # Check cache hit
    cache_status = "hit" if response_cache.get(f"products:{page}:{search}") else "miss"
    
    return create_response(
        data={
            "products": paginated_response.dict(),
            "cache_status": cache_status
        },
        message=f"Retrieved {len(paginated_products)} products"
    )


@router.post("/products/bulk-update")
def bulk_update_products(
    product_updates: List[dict]
):
    """Bulk update products with optimized batch processing.
    
    This demonstrates:
    1. Batch operations for bulk updates
    2. Performance optimization for bulk operations
    """
    
    def update_batch(batch: List[dict]) -> List[dict]:
        """Update a batch of products (mock implementation)."""
        results = []
        for update in batch:
            # Simulate update process
            result = {
                "id": update["id"],
                "status": "updated",
                "fields_updated": list(update.keys())
            }
            results.append(result)
        return results
    
    # Process updates in batches using the optimizer
    results = QueryOptimizer.batch_operations(batch_size=2)(update_batch)(product_updates)
    
    return create_response(
        data=results,
        message=f"Processed {len(results)} product updates"
    )


@router.get("/products/stats", response_model=APIResponse[dict])
def get_product_stats():
    """Get product statistics with optimized queries.
    
    This demonstrates:
    1. Single query optimization
    2. Efficient data aggregation
    """
    
    # Mock data for demonstration
    products = [
        {"id": 1, "price_gs": 1000, "stock_qty": 10},
        {"id": 2, "price_gs": 2000, "stock_qty": 5},
        {"id": 3, "price_gs": 1500, "stock_qty": 8},
        {"id": 4, "price_gs": 3000, "stock_qty": 2},
        {"id": 5, "price_gs": 2500, "stock_qty": 7},
    ]
    
    # Calculate statistics in a single pass
    stats = {
        "total_products": len(products),
        "total_value": sum(p["price_gs"] for p in products),
        "total_stock": sum(p["stock_qty"] for p in products),
        "average_price": sum(p["price_gs"] for p in products) / len(products)
    }
    
    return create_response(
        data=stats,
        message="Product statistics retrieved with optimized query"
    )


@router.get("/slow-operation")
def demonstrate_performance_timer():
    """Demonstrate performance timing.
    
    This demonstrates:
    1. Performance timing utilities
    2. Context manager for timing operations
    """
    from app.rms.api.performance import performance_timer
    import time
    
    def slow_operation():
        """Simulate a slow operation."""
        time.sleep(1)  # Simulate slow operation
        return {"result": "completed", "items_processed": 100}
    
    # Use performance timer to measure operation time
    with performance_timer("Slow operation demonstration"):
        result = slow_operation()
    
    return create_response(
        data=result,
        message="Operation completed with timing information"
    )


@router.get("/error-handling")
def demonstrate_error_handling():
    """Demonstrate standardized error handling.
    
    This demonstrates:
    1. Standardized error format
    2. Error codes and details
    """
    
    try:
        # Simulate an error
        raise ValueError("Invalid product ID")
    except ValueError as e:
        from app.rms.api.contracts import create_error, ErrorCode
        
        return create_error(
            error="Validation Error",
            message=str(e),
            code=ErrorCode.VALIDATION_ERROR,
            details={"field": "product_id", "received": "invalid_value"},
            request_id="req_12345"
        )