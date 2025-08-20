"""Performance monitoring API endpoints."""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from app.utils.performance import get_performance_monitor
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


class PerformanceSummaryResponse(BaseModel):
    """Response model for performance summary."""
    total_operations: int
    avg_duration: float
    min_duration: float
    max_duration: float
    avg_memory_delta: float
    slow_operations_count: int
    operation_breakdown: Dict[str, Dict[str, Any]]
    system_metrics_count: int


class SystemMetricResponse(BaseModel):
    """Response model for system metrics."""
    timestamp: str
    cpu_percent: float
    memory_percent: float
    memory_available: int
    memory_used: int
    disk_usage_percent: float
    disk_io_read_bytes: int
    disk_io_write_bytes: int
    network_io_bytes_sent: int
    network_io_bytes_recv: int
    active_connections: int
    thread_count: int
    process_count: int
    load_average: Optional[List[float]]


class SlowOperationResponse(BaseModel):
    """Response model for slow operations."""
    name: str
    duration: float
    timestamp: str
    correlation_id: Optional[str]
    context: Dict[str, Any]


class ProfileResponse(BaseModel):
    """Response model for profiling results."""
    name: str
    timestamp: str
    duration: float
    profile_output: str
    correlation_id: Optional[str]
    context: Dict[str, Any]


@router.get("/summary")
async def get_performance_summary() -> PerformanceSummaryResponse:
    """Get overall performance summary."""
    try:
        monitor = get_performance_monitor()
        summary = monitor.get_performance_summary()
        
        # Handle case where no data is available
        if "message" in summary:
            return PerformanceSummaryResponse(
                total_operations=0,
                avg_duration=0.0,
                min_duration=0.0,
                max_duration=0.0,
                avg_memory_delta=0.0,
                slow_operations_count=0,
                operation_breakdown={},
                system_metrics_count=0
            )
        
        return PerformanceSummaryResponse(**summary)
        
    except Exception as e:
        logger.error(f"Failed to get performance summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve performance summary")


@router.get("/system-metrics")
async def get_system_metrics(
    limit: int = Query(default=100, ge=1, le=1000)
) -> List[SystemMetricResponse]:
    """Get recent system performance metrics."""
    try:
        monitor = get_performance_monitor()
        metrics_data = monitor.get_system_metrics(limit)
        
        # Convert to response model
        response_metrics = []
        for metric_dict in metrics_data:
            response_metrics.append(SystemMetricResponse(**metric_dict))
        
        return response_metrics
        
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system metrics")


@router.get("/slow-operations")
async def get_slow_operations(
    limit: int = Query(default=50, ge=1, le=500)
) -> List[SlowOperationResponse]:
    """Get recent slow operations."""
    try:
        monitor = get_performance_monitor()
        slow_ops_data = monitor.get_slow_operations(limit)
        
        # Convert to response model
        response_ops = []
        for op_dict in slow_ops_data:
            # Convert datetime to ISO string if needed
            timestamp = op_dict["timestamp"]
            if isinstance(timestamp, datetime):
                timestamp = timestamp.isoformat()
            
            response_ops.append(SlowOperationResponse(
                name=op_dict["name"],
                duration=op_dict["duration"],
                timestamp=timestamp,
                correlation_id=op_dict.get("correlation_id"),
                context=op_dict.get("context", {})
            ))
        
        return response_ops
        
    except Exception as e:
        logger.error(f"Failed to get slow operations: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve slow operations")


@router.get("/profiles")
async def get_profiling_results(
    limit: int = Query(default=10, ge=1, le=100)
) -> List[ProfileResponse]:
    """Get recent profiling results."""
    try:
        monitor = get_performance_monitor()
        profiles_data = monitor.profiler.get_profiles(limit)
        
        # Convert to response model
        response_profiles = []
        for profile_dict in profiles_data:
            # Convert datetime to ISO string if needed
            timestamp = profile_dict["timestamp"]
            if isinstance(timestamp, datetime):
                timestamp = timestamp.isoformat()
            
            response_profiles.append(ProfileResponse(
                name=profile_dict["name"],
                timestamp=timestamp,
                duration=profile_dict["duration"],
                profile_output=profile_dict["profile_output"],
                correlation_id=profile_dict.get("correlation_id"),
                context=profile_dict.get("context", {})
            ))
        
        return response_profiles
        
    except Exception as e:
        logger.error(f"Failed to get profiling results: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve profiling results")


@router.delete("/profiles")
async def clear_profiling_results():
    """Clear stored profiling results."""
    try:
        monitor = get_performance_monitor()
        monitor.profiler.clear_profiles()
        
        return {"message": "Profiling results cleared successfully"}
        
    except Exception as e:
        logger.error(f"Failed to clear profiling results: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear profiling results")


@router.get("/status")
async def get_monitoring_status() -> Dict[str, Any]:
    """Get performance monitoring status."""
    try:
        monitor = get_performance_monitor()
        
        return {
            "monitoring_active": monitor._monitoring_active,
            "system_metric_interval": monitor.system_metric_interval,
            "metric_retention_hours": monitor.metric_retention_hours,
            "slow_query_threshold": monitor.slow_query_threshold,
            "memory_warning_threshold": monitor.memory_warning_threshold,
            "cpu_warning_threshold": monitor.cpu_warning_threshold,
            "gc_tracking_enabled": monitor.enable_gc_tracking,
            "stored_metrics_count": len(monitor.performance_metrics),
            "stored_system_metrics_count": len(monitor.system_metrics),
            "stored_slow_operations_count": len(monitor.slow_queries),
        }
        
    except Exception as e:
        logger.error(f"Failed to get monitoring status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve monitoring status")


@router.post("/start-monitoring")
async def start_performance_monitoring():
    """Start performance monitoring."""
    try:
        monitor = get_performance_monitor()
        await monitor.start_monitoring()
        
        return {"message": "Performance monitoring started successfully"}
        
    except Exception as e:
        logger.error(f"Failed to start performance monitoring: {e}")
        raise HTTPException(status_code=500, detail="Failed to start performance monitoring")


@router.post("/stop-monitoring")
async def stop_performance_monitoring():
    """Stop performance monitoring."""
    try:
        monitor = get_performance_monitor()
        await monitor.stop_monitoring()
        
        return {"message": "Performance monitoring stopped successfully"}
        
    except Exception as e:
        logger.error(f"Failed to stop performance monitoring: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop performance monitoring")


@router.get("/trends")
async def get_performance_trends(
    hours: int = Query(default=1, ge=1, le=24),
    metric: str = Query(default="cpu_percent", regex="^(cpu_percent|memory_percent|disk_usage_percent|active_connections|thread_count)$")
) -> Dict[str, Any]:
    """Get performance trends over time."""
    try:
        monitor = get_performance_monitor()
        
        # Get system metrics for the specified time range
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        # Filter and extract trend data
        trend_data = {
            "timestamps": [],
            "values": [],
            "metric_name": metric,
            "time_range_hours": hours,
        }
        
        with monitor._lock:
            for sys_metric in monitor.system_metrics:
                if sys_metric.timestamp >= cutoff:
                    trend_data["timestamps"].append(sys_metric.timestamp.isoformat())
                    
                    # Get the requested metric value
                    if hasattr(sys_metric, metric):
                        trend_data["values"].append(getattr(sys_metric, metric))
                    else:
                        trend_data["values"].append(0)
        
        return trend_data
        
    except Exception as e:
        logger.error(f"Failed to get performance trends: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve performance trends")


@router.get("/top-operations")
async def get_top_operations(
    limit: int = Query(default=10, ge=1, le=50),
    sort_by: str = Query(default="avg_duration", regex="^(avg_duration|max_duration|count)$")
) -> List[Dict[str, Any]]:
    """Get top operations by performance metrics."""
    try:
        monitor = get_performance_monitor()
        summary = monitor.get_performance_summary()
        
        if "operation_breakdown" not in summary:
            return []
        
        # Sort operations by the requested metric
        operations = []
        for name, stats in summary["operation_breakdown"].items():
            operations.append({
                "name": name,
                **stats
            })
        
        # Sort by the requested metric (descending)
        operations.sort(key=lambda x: x.get(sort_by, 0), reverse=True)
        
        return operations[:limit]
        
    except Exception as e:
        logger.error(f"Failed to get top operations: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve top operations")