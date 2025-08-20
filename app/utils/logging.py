"""Structured logging configuration for the application."""
import contextvars
import logging
import logging.config
import os
import sys
import uuid
from typing import Any, Dict, Optional

import structlog
from opentelemetry import trace

# Context variables for request tracking
correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar('correlation_id')
user_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('user_id', default=None)
request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('request_id', default=None)


def setup_logging() -> None:
    """Configure structured logging with OpenTelemetry integration."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            add_correlation_context,
            add_trace_info,
            add_service_context,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": structlog.processors.JSONRenderer(),
            },
            "console": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": structlog.dev.ConsoleRenderer(colors=True),
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "console" if sys.stderr.isatty() else "json",
                "stream": sys.stdout,
            },
        },
        "loggers": {
            "": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": True,
            },
            "uvicorn": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "handlers": ["console"],
                "level": "WARNING",  # Reduce SQL noise
                "propagate": False,
            },
        },
    }
    
    logging.config.dictConfig(logging_config)


def add_correlation_context(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add correlation and request context to log records."""
    try:
        correlation_id = correlation_id_var.get()
        event_dict["correlation_id"] = correlation_id
    except LookupError:
        # Generate new correlation ID if not set
        correlation_id = str(uuid.uuid4())
        correlation_id_var.set(correlation_id)
        event_dict["correlation_id"] = correlation_id
    
    try:
        user_id = user_id_var.get()
        if user_id:
            event_dict["user_id"] = user_id
    except LookupError:
        pass
    
    try:
        request_id = request_id_var.get()
        if request_id:
            event_dict["request_id"] = request_id
    except LookupError:
        pass
    
    return event_dict


def add_trace_info(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add OpenTelemetry trace information to log records."""
    span = trace.get_current_span()
    if span != trace.INVALID_SPAN:
        span_context = span.get_span_context()
        event_dict["trace_id"] = f"{span_context.trace_id:032x}"
        event_dict["span_id"] = f"{span_context.span_id:016x}"
    
    return event_dict


def add_service_context(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add service context information to log records."""
    event_dict["service"] = "kargo-amazon-dsp-integration"
    event_dict["version"] = os.getenv("APP_VERSION", "1.0.0")
    event_dict["environment"] = os.getenv("ENVIRONMENT", "development")
    
    # Add deployment information if available
    if os.getenv("DEPLOYMENT_ID"):
        event_dict["deployment_id"] = os.getenv("DEPLOYMENT_ID")
    
    if os.getenv("POD_NAME"):
        event_dict["pod_name"] = os.getenv("POD_NAME")
    
    if os.getenv("NODE_NAME"):
        event_dict["node_name"] = os.getenv("NODE_NAME")
    
    return event_dict


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID for the current context."""
    correlation_id_var.set(correlation_id)


def get_correlation_id() -> str:
    """Get or generate a correlation ID for the current context."""
    try:
        return correlation_id_var.get()
    except LookupError:
        correlation_id = str(uuid.uuid4())
        correlation_id_var.set(correlation_id)
        return correlation_id


def set_user_context(user_id: Optional[str] = None, request_id: Optional[str] = None) -> None:
    """Set user context information."""
    if user_id:
        user_id_var.set(user_id)
    if request_id:
        request_id_var.set(request_id)


def clear_context() -> None:
    """Clear all context variables."""
    for var in [correlation_id_var, user_id_var, request_id_var]:
        try:
            var.delete()
        except LookupError:
            pass


class LoggerMixin:
    """Mixin to provide logger functionality to classes."""
    
    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """Get logger for this class."""
        if not hasattr(self, '_logger'):
            self._logger = get_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        return self._logger


# Application-specific loggers
app_logger = get_logger("kargo_dsp.app")
creative_logger = get_logger("kargo_dsp.creative")
campaign_logger = get_logger("kargo_dsp.campaign")
amazon_logger = get_logger("kargo_dsp.amazon")
kargo_logger = get_logger("kargo_dsp.kargo")
metrics_logger = get_logger("kargo_dsp.metrics")
health_logger = get_logger("kargo_dsp.health")
security_logger = get_logger("kargo_dsp.security")