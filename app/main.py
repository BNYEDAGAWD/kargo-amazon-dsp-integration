"""
Kargo x Amazon DSP Integration
Production-Ready Creative Automation with Viewability Reporting
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import start_http_server
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import campaign, creative, health
from app.models.database import get_db_session
from app.utils.logging import setup_logging
from app.utils.metrics import setup_metrics


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    setup_logging()
    setup_metrics()
    
    # Initialize database
    async for session in get_db_session():
        # Run any startup checks
        break
    
    # Start Prometheus metrics server
    start_http_server(8001)
    
    logger = logging.getLogger(__name__)
    logger.info("Kargo x Amazon DSP Integration started successfully")
    
    yield
    
    # Shutdown
    logger.info("Kargo x Amazon DSP Integration shutting down")


# Create FastAPI application
app = FastAPI(
    title="Kargo x Amazon DSP Integration",
    description="""
    Production-Ready Creative Automation with Viewability Reporting
    
    This API provides:
    - Creative processing for Kargo formats (Runway Display, Enhanced Pre-Roll Video)
    - Amazon DSP integration with viewability measurement
    - Bulk sheet generation for campaign activation
    - Phased viewability implementation (Phase 1: DV-only, Phase 2: IAS S2S + DV)
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup OpenTelemetry instrumentation
FastAPIInstrumentor.instrument_app(app)
RequestsInstrumentor().instrument()
SQLAlchemyInstrumentor().instrument()

# Include routers
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(creative.router, prefix="/api/v1/creative", tags=["Creative"])
app.include_router(campaign.router, prefix="/api/v1/campaign", tags=["Campaign"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled errors."""
    logger = logging.getLogger(__name__)
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_id": str(trace.get_current_span().get_span_context().trace_id),
        }
    )


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint returning API information."""
    return {
        "name": "Kargo x Amazon DSP Integration",
        "version": "1.0.0",
        "description": "Production-Ready Creative Automation with Viewability Reporting",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_config=None,  # Use our custom logging setup
    )