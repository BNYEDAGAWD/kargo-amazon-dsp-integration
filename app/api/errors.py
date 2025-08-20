"""Error tracking API endpoints for monitoring and debugging."""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel

from app.utils.error_tracking import get_error_tracker, ErrorSeverity, ErrorCategory
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


class ErrorStatisticsResponse(BaseModel):
    """Response model for error statistics."""
    total_errors: int
    errors_last_hour: int
    errors_last_24h: int
    error_rate_per_hour: int
    category_breakdown: Dict[str, int]
    severity_breakdown: Dict[str, int]
    unique_errors: int
    alert_rules: int


class ErrorEventResponse(BaseModel):
    """Response model for error events."""
    id: str
    timestamp: str
    severity: str
    category: str
    message: str
    exception_type: str
    correlation_id: Optional[str]
    component: Optional[str]
    endpoint: Optional[str]
    count: int
    first_seen: Optional[str]
    last_seen: Optional[str]


@router.get("/statistics")
async def get_error_statistics() -> ErrorStatisticsResponse:
    """Get error statistics for monitoring dashboard."""
    try:
        tracker = get_error_tracker()
        stats = tracker.get_error_statistics()
        return ErrorStatisticsResponse(**stats)
    except Exception as e:
        logger.error(f"Failed to get error statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve error statistics")


@router.get("/recent")
async def get_recent_errors(
    limit: int = Query(default=50, ge=1, le=500),
    severity: Optional[ErrorSeverity] = Query(default=None),
    category: Optional[ErrorCategory] = Query(default=None),
    component: Optional[str] = Query(default=None),
    hours: int = Query(default=24, ge=1, le=168)  # Last 1-168 hours (7 days max)
) -> List[ErrorEventResponse]:
    """Get recent error events with filtering options."""
    try:
        tracker = get_error_tracker()
        
        # Filter by time window
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        filtered_errors = [
            error for error in tracker.error_history
            if error.timestamp > cutoff
        ]
        
        # Apply filters
        if severity:
            filtered_errors = [e for e in filtered_errors if e.severity == severity]
        
        if category:
            filtered_errors = [e for e in filtered_errors if e.category == category]
        
        if component:
            filtered_errors = [e for e in filtered_errors if e.component == component]
        
        # Sort by timestamp (most recent first) and limit
        filtered_errors.sort(key=lambda e: e.timestamp, reverse=True)
        filtered_errors = filtered_errors[:limit]
        
        # Convert to response model
        response_errors = []
        for error in filtered_errors:
            response_errors.append(ErrorEventResponse(
                id=error.id,
                timestamp=error.timestamp.isoformat(),
                severity=error.severity.value,
                category=error.category.value,
                message=error.message,
                exception_type=error.exception_type,
                correlation_id=error.correlation_id,
                component=error.component,
                endpoint=error.endpoint,
                count=error.count,
                first_seen=error.first_seen.isoformat() if error.first_seen else None,
                last_seen=error.last_seen.isoformat() if error.last_seen else None,
            ))
        
        return response_errors
        
    except Exception as e:
        logger.error(f"Failed to get recent errors: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve recent errors")


@router.get("/summary")
async def get_error_summary() -> List[Dict[str, Any]]:
    """Get aggregated error summary showing unique error patterns."""
    try:
        tracker = get_error_tracker()
        summary = tracker.aggregator.get_error_summary()
        return summary
    except Exception as e:
        logger.error(f"Failed to get error summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve error summary")


@router.get("/categories")
async def get_error_categories() -> List[str]:
    """Get list of available error categories."""
    return [category.value for category in ErrorCategory]


@router.get("/severities")
async def get_error_severities() -> List[str]:
    """Get list of available error severities."""
    return [severity.value for severity in ErrorSeverity]


@router.get("/components")
async def get_error_components(
    hours: int = Query(default=24, ge=1, le=168)
) -> List[str]:
    """Get list of components that have reported errors."""
    try:
        tracker = get_error_tracker()
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        components = set()
        for error in tracker.error_history:
            if error.timestamp > cutoff and error.component:
                components.add(error.component)
        
        return sorted(list(components))
        
    except Exception as e:
        logger.error(f"Failed to get error components: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve error components")


@router.get("/trends")
async def get_error_trends(
    hours: int = Query(default=24, ge=1, le=168),
    interval_minutes: int = Query(default=60, ge=5, le=360)  # 5 minutes to 6 hours
) -> Dict[str, Any]:
    """Get error trends over time."""
    try:
        tracker = get_error_tracker()
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        interval = timedelta(minutes=interval_minutes)
        
        # Create time buckets
        time_buckets = []
        current_time = cutoff
        while current_time < datetime.utcnow():
            time_buckets.append(current_time)
            current_time += interval
        
        # Count errors per time bucket
        trends = {
            "timestamps": [],
            "error_counts": [],
            "severity_breakdown": {severity.value: [] for severity in ErrorSeverity},
            "category_breakdown": {category.value: [] for category in ErrorCategory},
        }
        
        for i, bucket_start in enumerate(time_buckets):
            bucket_end = bucket_start + interval if i < len(time_buckets) - 1 else datetime.utcnow()
            trends["timestamps"].append(bucket_start.isoformat())
            
            # Count errors in this time bucket
            bucket_errors = [
                error for error in tracker.error_history
                if bucket_start <= error.timestamp < bucket_end
            ]
            
            trends["error_counts"].append(len(bucket_errors))
            
            # Count by severity
            for severity in ErrorSeverity:
                count = sum(1 for e in bucket_errors if e.severity == severity)
                trends["severity_breakdown"][severity.value].append(count)
            
            # Count by category
            for category in ErrorCategory:
                count = sum(1 for e in bucket_errors if e.category == category)
                trends["category_breakdown"][category.value].append(count)
        
        return trends
        
    except Exception as e:
        logger.error(f"Failed to get error trends: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve error trends")


@router.post("/test-error")
async def test_error_tracking(
    severity: ErrorSeverity = ErrorSeverity.LOW,
    category: ErrorCategory = ErrorCategory.INTERNAL_ERROR,
    message: str = "Test error for monitoring"
):
    """Test endpoint to generate sample errors for testing monitoring systems."""
    try:
        # Create a test exception
        test_exception = RuntimeError(message)
        
        # Track the error
        tracker = get_error_tracker()
        error_event = tracker.track_error(
            exception=test_exception,
            severity=severity,
            category=category,
            component="error_api",
            context={"test": True, "endpoint": "/errors/test-error"}
        )
        
        return {
            "message": "Test error generated successfully",
            "error_id": error_event.id,
            "severity": severity.value,
            "category": category.value,
        }
        
    except Exception as e:
        logger.error(f"Failed to generate test error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate test error")