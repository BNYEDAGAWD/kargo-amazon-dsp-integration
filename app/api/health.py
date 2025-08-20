"""Health check endpoints for monitoring and observability."""
import asyncio
import os
import psutil
from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db_session, check_database_health
from app.services.amazon_client import get_amazon_dsp_client
from app.services.kargo_client import get_kargo_client
from app.utils.logging import health_logger
from app.utils.metrics import MetricsCollector, REGISTRY
from prometheus_client import generate_latest

router = APIRouter()

# Health check state
_startup_time = datetime.utcnow()
_health_state = {
    "database": {"status": "unknown", "last_check": None, "error": None},
    "amazon_dsp": {"status": "unknown", "last_check": None, "error": None},
    "kargo": {"status": "unknown", "last_check": None, "error": None},
}


@router.get("/")
async def health_check() -> Dict[str, Any]:
    """Basic health check endpoint."""
    uptime = datetime.utcnow() - _startup_time
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "kargo-amazon-dsp-integration",
        "version": os.getenv("APP_VERSION", "1.0.0"),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "uptime_seconds": int(uptime.total_seconds()),
        "uptime_human": str(uptime),
    }


@router.get("/ready")
async def readiness_check() -> Dict[str, Any]:
    """Readiness check including all external dependencies."""
    checks = await _perform_health_checks()
    
    # Determine overall status
    all_healthy = all(check["status"] == "healthy" for check in checks.values())
    overall_status = "ready" if all_healthy else "not_ready"
    http_status = 200 if all_healthy else 503
    
    response = {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
    }
    
    if not all_healthy:
        health_logger.warning("Readiness check failed", checks=checks)
        raise HTTPException(status_code=http_status, detail=response)
    
    return response


@router.get("/live")
async def liveness_check() -> Dict[str, Any]:
    """Liveness check for container orchestration."""
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": int((datetime.utcnow() - _startup_time).total_seconds()),
    }


@router.get("/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """Detailed health check with system metrics."""
    # Get system metrics
    process = psutil.Process()
    memory_info = process.memory_info()
    
    # Perform health checks
    checks = await _perform_health_checks()
    all_healthy = all(check["status"] == "healthy" for check in checks.values())
    
    # Get disk usage for temp directory
    disk_usage = psutil.disk_usage("/tmp")
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "service_info": {
            "name": "kargo-amazon-dsp-integration",
            "version": os.getenv("APP_VERSION", "1.0.0"),
            "environment": os.getenv("ENVIRONMENT", "development"),
            "uptime_seconds": int((datetime.utcnow() - _startup_time).total_seconds()),
        },
        "system_metrics": {
            "memory": {
                "rss_bytes": memory_info.rss,
                "vms_bytes": memory_info.vms,
                "percent": process.memory_percent(),
            },
            "cpu": {
                "percent": process.cpu_percent(),
                "threads": process.num_threads(),
            },
            "disk": {
                "total_bytes": disk_usage.total,
                "used_bytes": disk_usage.used,
                "free_bytes": disk_usage.free,
                "percent_used": (disk_usage.used / disk_usage.total) * 100,
            },
            "file_descriptors": {
                "open": process.num_fds() if hasattr(process, 'num_fds') else None,
            }
        },
        "dependency_checks": checks,
    }


@router.get("/metrics")
async def metrics_endpoint():
    """Prometheus metrics endpoint."""
    # Update system metrics
    process = psutil.Process()
    memory_info = process.memory_info()
    
    MetricsCollector.set_memory_usage("rss", memory_info.rss)
    MetricsCollector.set_memory_usage("vms", memory_info.vms)
    
    # Update external service health metrics
    checks = await _perform_health_checks()
    for service, check in checks.items():
        is_healthy = check["status"] == "healthy"
        MetricsCollector.set_external_service_health(service, is_healthy)
    
    # Return Prometheus formatted metrics
    return generate_latest(REGISTRY).decode("utf-8")


async def _perform_health_checks() -> Dict[str, Dict[str, Any]]:
    """Perform health checks on all external dependencies."""
    now = datetime.utcnow()
    checks = {}
    
    # Database health check
    try:
        is_healthy = await check_database_health()
        checks["database"] = {
            "status": "healthy" if is_healthy else "unhealthy",
            "last_check": now.isoformat(),
            "error": None,
            "response_time_ms": None,
        }
        _health_state["database"] = checks["database"]
    except Exception as e:
        error_msg = str(e)
        checks["database"] = {
            "status": "unhealthy",
            "last_check": now.isoformat(),
            "error": error_msg,
            "response_time_ms": None,
        }
        _health_state["database"] = checks["database"]
        health_logger.error("Database health check failed", error=error_msg)
    
    # Amazon DSP health check (mock client connectivity)
    try:
        start_time = datetime.utcnow()
        amazon_client = await get_amazon_dsp_client()
        # Basic connectivity test - check mock data summary
        summary = amazon_client.get_mock_data_summary()
        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        checks["amazon_dsp"] = {
            "status": "healthy",
            "last_check": now.isoformat(),
            "error": None,
            "response_time_ms": round(response_time, 2),
            "data": {
                "creatives_count": summary.get("creatives", 0),
                "campaigns_count": summary.get("campaigns", 0),
            }
        }
        _health_state["amazon_dsp"] = checks["amazon_dsp"]
    except Exception as e:
        error_msg = str(e)
        checks["amazon_dsp"] = {
            "status": "unhealthy",
            "last_check": now.isoformat(),
            "error": error_msg,
            "response_time_ms": None,
        }
        _health_state["amazon_dsp"] = checks["amazon_dsp"]
        health_logger.error("Amazon DSP health check failed", error=error_msg)
    
    # Kargo API health check (mock client connectivity)  
    try:
        start_time = datetime.utcnow()
        kargo_client = await get_kargo_client()
        # Basic connectivity test
        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        checks["kargo"] = {
            "status": "healthy",
            "last_check": now.isoformat(),
            "error": None,
            "response_time_ms": round(response_time, 2),
        }
        _health_state["kargo"] = checks["kargo"]
    except Exception as e:
        error_msg = str(e)
        checks["kargo"] = {
            "status": "unhealthy", 
            "last_check": now.isoformat(),
            "error": error_msg,
            "response_time_ms": None,
        }
        _health_state["kargo"] = checks["kargo"]
        health_logger.error("Kargo health check failed", error=error_msg)
    
    return checks


@router.get("/status")
async def service_status() -> Dict[str, Any]:
    """Service status endpoint with cached health check results."""
    return {
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "cached_checks": _health_state,
        "uptime_seconds": int((datetime.utcnow() - _startup_time).total_seconds()),
    }