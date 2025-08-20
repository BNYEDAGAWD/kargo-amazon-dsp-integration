"""Error tracking and alerting system."""
import asyncio
import json
import traceback
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import threading
from contextlib import contextmanager

from app.utils.logging import get_logger, get_correlation_id
from app.utils.metrics import MetricsCollector

logger = get_logger(__name__)


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Error categories for classification."""
    API_ERROR = "api_error"
    DATABASE_ERROR = "database_error"
    VALIDATION_ERROR = "validation_error"
    EXTERNAL_SERVICE_ERROR = "external_service_error"
    AUTHENTICATION_ERROR = "authentication_error"
    PERMISSION_ERROR = "permission_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    TIMEOUT_ERROR = "timeout_error"
    NETWORK_ERROR = "network_error"
    CONFIGURATION_ERROR = "configuration_error"
    INTERNAL_ERROR = "internal_error"
    USER_ERROR = "user_error"


@dataclass
class ErrorEvent:
    """Represents an error event for tracking and alerting."""
    id: str
    timestamp: datetime
    severity: ErrorSeverity
    category: ErrorCategory
    message: str
    exception_type: str
    stack_trace: str
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    component: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    count: int = 1
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    
    def __post_init__(self):
        if self.first_seen is None:
            self.first_seen = self.timestamp
        if self.last_seen is None:
            self.last_seen = self.timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        return data
    
    def fingerprint(self) -> str:
        """Generate a unique fingerprint for grouping similar errors."""
        components = [
            self.exception_type,
            self.category.value,
            self.component or "unknown",
            # First few lines of stack trace for similarity
            "\n".join(self.stack_trace.split("\n")[:5]),
        ]
        return hash(tuple(components))


class ErrorAggregator:
    """Aggregates similar errors to reduce noise."""
    
    def __init__(self, max_size: int = 1000, time_window: int = 300):
        self.max_size = max_size
        self.time_window = timedelta(seconds=time_window)
        self.errors: Dict[str, ErrorEvent] = {}
        self._lock = threading.RLock()
    
    def add_error(self, error: ErrorEvent) -> ErrorEvent:
        """Add an error event, aggregating with existing similar errors."""
        fingerprint = str(error.fingerprint())
        
        with self._lock:
            if fingerprint in self.errors:
                existing = self.errors[fingerprint]
                # Update existing error
                existing.count += 1
                existing.last_seen = error.timestamp
                # Keep the most severe level
                if error.severity.value > existing.severity.value:
                    existing.severity = error.severity
                return existing
            else:
                # Clean old errors if we're at capacity
                if len(self.errors) >= self.max_size:
                    self._cleanup_old_errors()
                
                self.errors[fingerprint] = error
                return error
    
    def _cleanup_old_errors(self):
        """Remove errors older than the time window."""
        cutoff = datetime.utcnow() - self.time_window
        to_remove = [
            fp for fp, error in self.errors.items()
            if error.last_seen < cutoff
        ]
        for fp in to_remove:
            del self.errors[fp]
    
    def get_error_summary(self) -> List[Dict[str, Any]]:
        """Get summary of current errors."""
        with self._lock:
            return [error.to_dict() for error in self.errors.values()]


class AlertRule:
    """Defines conditions for triggering alerts."""
    
    def __init__(
        self,
        name: str,
        condition: callable,
        severity: ErrorSeverity,
        cooldown_seconds: int = 300,
        enabled: bool = True
    ):
        self.name = name
        self.condition = condition
        self.severity = severity
        self.cooldown_seconds = cooldown_seconds
        self.enabled = enabled
        self.last_triggered: Optional[datetime] = None
    
    def should_trigger(self, error: ErrorEvent) -> bool:
        """Check if this rule should trigger for the given error."""
        if not self.enabled:
            return False
        
        # Check cooldown
        if self.last_triggered:
            if (datetime.utcnow() - self.last_triggered).total_seconds() < self.cooldown_seconds:
                return False
        
        # Check condition
        if self.condition(error):
            self.last_triggered = datetime.utcnow()
            return True
        
        return False


class ErrorTracker:
    """Main error tracking and alerting system."""
    
    def __init__(self):
        self.aggregator = ErrorAggregator()
        self.alert_rules: List[AlertRule] = []
        self.error_history = deque(maxlen=10000)  # Keep last 10k errors
        self.alert_handlers: List[callable] = []
        self._setup_default_rules()
    
    def _setup_default_rules(self):
        """Setup default alerting rules."""
        # Critical errors always alert
        self.add_alert_rule(
            name="critical_errors",
            condition=lambda e: e.severity == ErrorSeverity.CRITICAL,
            severity=ErrorSeverity.CRITICAL,
            cooldown_seconds=60
        )
        
        # High error rate
        self.add_alert_rule(
            name="high_error_rate",
            condition=lambda e: self._is_high_error_rate(e),
            severity=ErrorSeverity.HIGH,
            cooldown_seconds=300
        )
        
        # Database errors
        self.add_alert_rule(
            name="database_errors",
            condition=lambda e: e.category == ErrorCategory.DATABASE_ERROR and e.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL],
            severity=ErrorSeverity.HIGH,
            cooldown_seconds=180
        )
        
        # External service failures
        self.add_alert_rule(
            name="external_service_failures",
            condition=lambda e: e.category == ErrorCategory.EXTERNAL_SERVICE_ERROR and e.count > 5,
            severity=ErrorSeverity.MEDIUM,
            cooldown_seconds=300
        )
    
    def _is_high_error_rate(self, error: ErrorEvent) -> bool:
        """Check if we're experiencing a high error rate."""
        # Count errors in the last 5 minutes
        cutoff = datetime.utcnow() - timedelta(minutes=5)
        recent_errors = sum(
            1 for e in self.error_history
            if e.timestamp > cutoff
        )
        return recent_errors > 50  # More than 50 errors in 5 minutes
    
    def add_alert_rule(self, name: str, condition: callable, severity: ErrorSeverity, cooldown_seconds: int = 300):
        """Add a custom alert rule."""
        rule = AlertRule(name, condition, severity, cooldown_seconds)
        self.alert_rules.append(rule)
        logger.info(f"Added alert rule: {name}")
    
    def add_alert_handler(self, handler: callable):
        """Add an alert handler function."""
        self.alert_handlers.append(handler)
        logger.info(f"Added alert handler: {handler.__name__}")
    
    def track_error(
        self,
        exception: Exception,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.INTERNAL_ERROR,
        component: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        endpoint: Optional[str] = None,
        method: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> ErrorEvent:
        """Track an error event."""
        import uuid
        
        # Create error event
        error = ErrorEvent(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            severity=severity,
            category=category,
            message=str(exception),
            exception_type=exception.__class__.__name__,
            stack_trace=traceback.format_exc(),
            correlation_id=get_correlation_id(),
            user_id=user_id,
            component=component,
            endpoint=endpoint,
            method=method,
            context=context or {}
        )
        
        # Aggregate similar errors
        aggregated_error = self.aggregator.add_error(error)
        
        # Add to history
        self.error_history.append(aggregated_error)
        
        # Log the error
        logger.error(
            f"Error tracked: {exception}",
            extra={
                "error_id": error.id,
                "severity": severity.value,
                "category": category.value,
                "component": component,
                "exception_type": exception.__class__.__name__,
                "context": context
            }
        )
        
        # Update metrics
        MetricsCollector.record_error(
            component=component or "unknown",
            error_type=exception.__class__.__name__,
            severity=severity.value
        )
        
        # Check alert rules
        self._check_alert_rules(aggregated_error)
        
        return aggregated_error
    
    def _check_alert_rules(self, error: ErrorEvent):
        """Check if any alert rules should trigger."""
        for rule in self.alert_rules:
            try:
                if rule.should_trigger(error):
                    self._trigger_alert(rule, error)
            except Exception as e:
                logger.error(f"Error in alert rule {rule.name}: {e}")
    
    def _trigger_alert(self, rule: AlertRule, error: ErrorEvent):
        """Trigger an alert."""
        alert_data = {
            "rule_name": rule.name,
            "severity": rule.severity.value,
            "error": error.to_dict(),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        logger.warning(f"Alert triggered: {rule.name}", extra=alert_data)
        
        # Call alert handlers
        for handler in self.alert_handlers:
            try:
                asyncio.create_task(self._run_alert_handler(handler, alert_data))
            except Exception as e:
                logger.error(f"Error in alert handler {handler.__name__}: {e}")
    
    async def _run_alert_handler(self, handler: callable, alert_data: Dict[str, Any]):
        """Run an alert handler asynchronously."""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(alert_data)
            else:
                handler(alert_data)
        except Exception as e:
            logger.error(f"Alert handler {handler.__name__} failed: {e}")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics for monitoring."""
        cutoff_1h = datetime.utcnow() - timedelta(hours=1)
        cutoff_24h = datetime.utcnow() - timedelta(hours=24)
        
        recent_errors_1h = [e for e in self.error_history if e.timestamp > cutoff_1h]
        recent_errors_24h = [e for e in self.error_history if e.timestamp > cutoff_24h]
        
        # Group by category and severity
        category_counts = defaultdict(int)
        severity_counts = defaultdict(int)
        
        for error in recent_errors_24h:
            category_counts[error.category.value] += error.count
            severity_counts[error.severity.value] += error.count
        
        return {
            "total_errors": len(self.error_history),
            "errors_last_hour": len(recent_errors_1h),
            "errors_last_24h": len(recent_errors_24h),
            "error_rate_per_hour": len(recent_errors_1h),
            "category_breakdown": dict(category_counts),
            "severity_breakdown": dict(severity_counts),
            "unique_errors": len(self.aggregator.errors),
            "alert_rules": len(self.alert_rules),
        }


# Global error tracker instance
error_tracker = ErrorTracker()


def get_error_tracker() -> ErrorTracker:
    """Get the global error tracker instance."""
    return error_tracker


@contextmanager
def track_errors(
    component: str,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    category: ErrorCategory = ErrorCategory.INTERNAL_ERROR,
    context: Optional[Dict[str, Any]] = None,
    reraise: bool = True
):
    """Context manager to automatically track errors."""
    try:
        yield
    except Exception as e:
        error_tracker.track_error(
            exception=e,
            severity=severity,
            category=category,
            component=component,
            context=context
        )
        if reraise:
            raise


def track_error(
    exception: Exception,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    category: ErrorCategory = ErrorCategory.INTERNAL_ERROR,
    component: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> ErrorEvent:
    """Track a single error."""
    return error_tracker.track_error(
        exception=exception,
        severity=severity,
        category=category,
        component=component,
        context=context
    )


# Default alert handlers
async def log_alert_handler(alert_data: Dict[str, Any]):
    """Default alert handler that logs alerts."""
    logger.warning(
        f"ALERT: {alert_data['rule_name']}",
        extra={
            "alert_rule": alert_data["rule_name"],
            "alert_severity": alert_data["severity"],
            "error_message": alert_data["error"]["message"],
            "error_count": alert_data["error"]["count"],
        }
    )


# Register default handler
error_tracker.add_alert_handler(log_alert_handler)