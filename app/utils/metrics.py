"""Prometheus metrics configuration and collection."""
import time
from typing import Dict, Optional

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.resources import Resource


# Prometheus metrics registry
REGISTRY = CollectorRegistry()

# Application metrics
CREATIVE_PROCESSING_REQUESTS = Counter(
    'creative_processing_requests_total',
    'Total number of creative processing requests',
    ['format', 'phase', 'status'],
    registry=REGISTRY
)

CREATIVE_PROCESSING_DURATION = Histogram(
    'creative_processing_duration_seconds',
    'Time spent processing creatives',
    ['format', 'phase'],
    registry=REGISTRY
)

CAMPAIGN_OPERATIONS = Counter(
    'campaign_operations_total',
    'Total number of campaign operations',
    ['operation', 'status'],
    registry=REGISTRY
)

BULK_SHEET_GENERATION = Counter(
    'bulk_sheet_generation_total',
    'Total number of bulk sheet generations',
    ['status'],
    registry=REGISTRY
)

BULK_SHEET_GENERATION_DURATION = Histogram(
    'bulk_sheet_generation_duration_seconds',
    'Time spent generating bulk sheets',
    registry=REGISTRY
)

AMAZON_DSP_API_REQUESTS = Counter(
    'amazon_dsp_api_requests_total',
    'Total number of Amazon DSP API requests',
    ['endpoint', 'method', 'status_code'],
    registry=REGISTRY
)

AMAZON_DSP_API_DURATION = Histogram(
    'amazon_dsp_api_request_duration_seconds',
    'Time spent on Amazon DSP API requests',
    ['endpoint', 'method'],
    registry=REGISTRY
)

KARGO_API_REQUESTS = Counter(
    'kargo_api_requests_total',
    'Total number of Kargo API requests',
    ['endpoint', 'status_code'],
    registry=REGISTRY
)

KARGO_API_DURATION = Histogram(
    'kargo_api_request_duration_seconds',
    'Time spent on Kargo API requests',
    ['endpoint'],
    registry=REGISTRY
)

DATABASE_OPERATIONS = Counter(
    'database_operations_total',
    'Total number of database operations',
    ['operation', 'table', 'status'],
    registry=REGISTRY
)

DATABASE_OPERATION_DURATION = Histogram(
    'database_operation_duration_seconds',
    'Time spent on database operations',
    ['operation', 'table'],
    registry=REGISTRY
)

ACTIVE_CAMPAIGNS = Gauge(
    'active_campaigns',
    'Number of active campaigns',
    registry=REGISTRY
)

PROCESSED_CREATIVES = Gauge(
    'processed_creatives_total',
    'Total number of processed creatives',
    ['format', 'phase'],
    registry=REGISTRY
)

VIEWABILITY_REPORTS = Counter(
    'viewability_reports_total',
    'Total number of viewability reports processed',
    ['vendor', 'campaign_phase'],
    registry=REGISTRY
)

ERROR_RATE = Counter(
    'errors_total',
    'Total number of errors',
    ['component', 'error_type', 'severity'],
    registry=REGISTRY
)

HTTP_REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint', 'status_code'],
    registry=REGISTRY
)

HTTP_REQUESTS_TOTAL = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code'],
    registry=REGISTRY
)

CONCURRENT_REQUESTS = Gauge(
    'concurrent_requests',
    'Number of concurrent HTTP requests',
    registry=REGISTRY
)

MEMORY_USAGE = Gauge(
    'memory_usage_bytes',
    'Memory usage in bytes',
    ['type'],
    registry=REGISTRY
)

CACHE_OPERATIONS = Counter(
    'cache_operations_total',
    'Total cache operations',
    ['operation', 'cache_type', 'result'],
    registry=REGISTRY
)

BACKGROUND_TASKS = Gauge(
    'background_tasks',
    'Number of background tasks',
    ['task_type', 'status'],
    registry=REGISTRY
)

QUEUE_SIZE = Gauge(
    'queue_size',
    'Size of processing queues',
    ['queue_name'],
    registry=REGISTRY
)

EXTERNAL_SERVICE_HEALTH = Gauge(
    'external_service_health',
    'Health status of external services (1=healthy, 0=unhealthy)',
    ['service_name'],
    registry=REGISTRY
)


def setup_metrics() -> None:
    """Setup OpenTelemetry metrics with Prometheus exporter."""
    # Create resource
    resource = Resource(attributes={
        "service.name": "kargo-amazon-dsp-integration",
        "service.version": "1.0.0",
    })
    
    # Setup metric reader
    reader = PrometheusMetricReader()
    
    # Setup meter provider
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(provider)


class MetricsCollector:
    """Helper class for collecting application metrics."""
    
    @staticmethod
    def record_creative_processing(
        format: str, 
        phase: str, 
        duration: float, 
        status: str = "success"
    ) -> None:
        """Record creative processing metrics."""
        CREATIVE_PROCESSING_REQUESTS.labels(
            format=format, 
            phase=phase, 
            status=status
        ).inc()
        
        CREATIVE_PROCESSING_DURATION.labels(
            format=format, 
            phase=phase
        ).observe(duration)
    
    @staticmethod
    def record_campaign_operation(operation: str, status: str = "success") -> None:
        """Record campaign operation metrics."""
        CAMPAIGN_OPERATIONS.labels(
            operation=operation, 
            status=status
        ).inc()
    
    @staticmethod
    def record_bulk_sheet_generation(duration: float, status: str = "success") -> None:
        """Record bulk sheet generation metrics."""
        BULK_SHEET_GENERATION.labels(status=status).inc()
        BULK_SHEET_GENERATION_DURATION.observe(duration)
    
    @staticmethod
    def record_amazon_dsp_request(
        endpoint: str, 
        method: str, 
        status_code: int, 
        duration: float
    ) -> None:
        """Record Amazon DSP API request metrics."""
        AMAZON_DSP_API_REQUESTS.labels(
            endpoint=endpoint, 
            method=method, 
            status_code=str(status_code)
        ).inc()
        
        AMAZON_DSP_API_DURATION.labels(
            endpoint=endpoint, 
            method=method
        ).observe(duration)
    
    @staticmethod
    def record_kargo_request(
        endpoint: str, 
        status_code: int, 
        duration: float
    ) -> None:
        """Record Kargo API request metrics."""
        KARGO_API_REQUESTS.labels(
            endpoint=endpoint, 
            status_code=str(status_code)
        ).inc()
        
        KARGO_API_DURATION.labels(endpoint=endpoint).observe(duration)
    
    @staticmethod
    def record_database_operation(
        operation: str, 
        table: str, 
        duration: float, 
        status: str = "success"
    ) -> None:
        """Record database operation metrics."""
        DATABASE_OPERATIONS.labels(
            operation=operation, 
            table=table, 
            status=status
        ).inc()
        
        DATABASE_OPERATION_DURATION.labels(
            operation=operation, 
            table=table
        ).observe(duration)
    
    @staticmethod
    def set_active_campaigns(count: int) -> None:
        """Set number of active campaigns."""
        ACTIVE_CAMPAIGNS.set(count)
    
    @staticmethod
    def set_processed_creatives(count: int, format: str, phase: str) -> None:
        """Set number of processed creatives."""
        PROCESSED_CREATIVES.labels(format=format, phase=phase).set(count)
    
    @staticmethod
    def record_viewability_report(vendor: str, campaign_phase: str) -> None:
        """Record viewability report processing."""
        VIEWABILITY_REPORTS.labels(
            vendor=vendor, 
            campaign_phase=campaign_phase
        ).inc()
    
    @staticmethod
    def record_error(component: str, error_type: str, severity: str = "error") -> None:
        """Record application errors."""
        ERROR_RATE.labels(
            component=component, 
            error_type=error_type,
            severity=severity
        ).inc()
    
    @staticmethod
    def record_http_request(
        method: str,
        endpoint: str,
        status_code: int,
        duration: float
    ) -> None:
        """Record HTTP request metrics."""
        HTTP_REQUESTS_TOTAL.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).inc()
        
        HTTP_REQUEST_DURATION.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).observe(duration)
    
    @staticmethod
    def set_concurrent_requests(count: int) -> None:
        """Set number of concurrent requests."""
        CONCURRENT_REQUESTS.set(count)
    
    @staticmethod
    def set_memory_usage(memory_type: str, bytes_used: int) -> None:
        """Set memory usage metrics."""
        MEMORY_USAGE.labels(type=memory_type).set(bytes_used)
    
    @staticmethod
    def record_cache_operation(
        operation: str,
        cache_type: str,
        result: str
    ) -> None:
        """Record cache operation metrics."""
        CACHE_OPERATIONS.labels(
            operation=operation,
            cache_type=cache_type,
            result=result
        ).inc()
    
    @staticmethod
    def set_background_tasks(task_type: str, status: str, count: int) -> None:
        """Set number of background tasks."""
        BACKGROUND_TASKS.labels(
            task_type=task_type,
            status=status
        ).set(count)
    
    @staticmethod
    def set_queue_size(queue_name: str, size: int) -> None:
        """Set queue size metric."""
        QUEUE_SIZE.labels(queue_name=queue_name).set(size)
    
    @staticmethod
    def set_external_service_health(service_name: str, is_healthy: bool) -> None:
        """Set external service health status."""
        EXTERNAL_SERVICE_HEALTH.labels(service_name=service_name).set(1 if is_healthy else 0)
    
    @staticmethod
    def record_campaign_created(phase: str, creative_count: int) -> None:
        """Record campaign creation."""
        CAMPAIGN_OPERATIONS.labels(operation="create", status="success").inc()
    
    @staticmethod
    def record_campaign_activated(campaign_id: str) -> None:
        """Record campaign activation.""" 
        CAMPAIGN_OPERATIONS.labels(operation="activate", status="success").inc()


class TimingContext:
    """Context manager for timing operations."""
    
    def __init__(self, metric_func, *args, **kwargs):
        self.metric_func = metric_func
        self.args = args
        self.kwargs = kwargs
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        
        # Determine status based on exception
        status = "error" if exc_type else "success"
        
        # Call the metric function with duration and status
        self.metric_func(*self.args, duration=duration, status=status, **self.kwargs)


# Convenience functions for timing
def time_creative_processing(format: str, phase: str):
    """Context manager for timing creative processing."""
    return TimingContext(
        MetricsCollector.record_creative_processing,
        format, phase
    )


def time_bulk_sheet_generation():
    """Context manager for timing bulk sheet generation."""
    return TimingContext(MetricsCollector.record_bulk_sheet_generation)


def time_database_operation(operation: str, table: str):
    """Context manager for timing database operations."""
    return TimingContext(
        MetricsCollector.record_database_operation,
        operation, table
    )