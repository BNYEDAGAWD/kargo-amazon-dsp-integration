"""Performance monitoring and profiling utilities."""
import asyncio
import cProfile
import functools
import gc
import io
import pstats
import psutil
import time
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable, Generator
from collections import defaultdict, deque
import weakref

from app.utils.logging import get_logger, get_correlation_id
from app.utils.metrics import MetricsCollector

logger = get_logger(__name__)


@dataclass
class PerformanceMetric:
    """Represents a performance measurement."""
    name: str
    start_time: float
    end_time: float
    duration: float
    memory_before: float
    memory_after: float
    memory_delta: float
    correlation_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_ms(self) -> float:
        """Duration in milliseconds."""
        return self.duration * 1000


@dataclass
class SystemMetrics:
    """System-wide performance metrics."""
    timestamp: datetime
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
    load_average: Optional[List[float]] = None  # Unix only
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "memory_available": self.memory_available,
            "memory_used": self.memory_used,
            "disk_usage_percent": self.disk_usage_percent,
            "disk_io_read_bytes": self.disk_io_read_bytes,
            "disk_io_write_bytes": self.disk_io_write_bytes,
            "network_io_bytes_sent": self.network_io_bytes_sent,
            "network_io_bytes_recv": self.network_io_bytes_recv,
            "active_connections": self.active_connections,
            "thread_count": self.thread_count,
            "process_count": self.process_count,
            "load_average": self.load_average,
        }


class PerformanceProfiler:
    """Performance profiler for detailed code analysis."""
    
    def __init__(self, max_profiles: int = 100):
        self.max_profiles = max_profiles
        self.profiles: deque = deque(maxlen=max_profiles)
        self.active_profiles: Dict[str, cProfile.Profile] = {}
        self._lock = threading.RLock()
    
    @contextmanager
    def profile(self, name: str, context: Optional[Dict[str, Any]] = None):
        """Context manager for profiling code blocks."""
        profile_id = f"{name}_{time.time()}"
        profiler = cProfile.Profile()
        
        with self._lock:
            self.active_profiles[profile_id] = profiler
        
        try:
            profiler.enable()
            start_time = time.time()
            yield
        finally:
            end_time = time.time()
            profiler.disable()
            
            with self._lock:
                self.active_profiles.pop(profile_id, None)
            
            # Store profile result
            self._store_profile_result(name, profiler, start_time, end_time, context)
    
    def _store_profile_result(
        self, 
        name: str, 
        profiler: cProfile.Profile, 
        start_time: float, 
        end_time: float,
        context: Optional[Dict[str, Any]]
    ):
        """Store profiling result."""
        # Convert profile to string
        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.sort_stats('cumulative')
        stats.print_stats(20)  # Top 20 functions
        
        profile_data = {
            "name": name,
            "timestamp": datetime.utcnow(),
            "duration": end_time - start_time,
            "profile_output": stream.getvalue(),
            "correlation_id": get_correlation_id(),
            "context": context or {},
        }
        
        with self._lock:
            self.profiles.append(profile_data)
        
        logger.debug(f"Profile completed: {name}, duration: {end_time - start_time:.4f}s")
    
    def get_profiles(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent profiling results."""
        with self._lock:
            return list(self.profiles)[-limit:]
    
    def clear_profiles(self):
        """Clear stored profiles."""
        with self._lock:
            self.profiles.clear()


class PerformanceMonitor:
    """Main performance monitoring system."""
    
    def __init__(self, 
                 metric_retention_hours: int = 24,
                 system_metric_interval: int = 60,
                 enable_gc_tracking: bool = True):
        self.metric_retention_hours = metric_retention_hours
        self.system_metric_interval = system_metric_interval
        self.enable_gc_tracking = enable_gc_tracking
        
        # Storage
        self.performance_metrics: deque = deque()
        self.system_metrics: deque = deque()
        self.slow_queries: deque = deque(maxlen=1000)
        
        # Profiler
        self.profiler = PerformanceProfiler()
        
        # System monitoring
        self._system_monitor_task: Optional[asyncio.Task] = None
        self._monitoring_active = False
        
        # Thresholds
        self.slow_query_threshold = 1.0  # 1 second
        self.memory_warning_threshold = 0.8  # 80%
        self.cpu_warning_threshold = 0.9  # 90%
        
        # GC tracking
        if self.enable_gc_tracking:
            self._setup_gc_callbacks()
        
        # Thread safety
        self._lock = threading.RLock()
    
    def _setup_gc_callbacks(self):
        """Setup garbage collection tracking."""
        def gc_callback(phase, info):
            if phase == 'start':
                logger.debug(f"GC started: generation {info['generation']}")
            elif phase == 'stop':
                logger.debug(
                    f"GC completed: generation {info['generation']}, "
                    f"collected {info['collected']} objects"
                )
        
        gc.callbacks.append(gc_callback)
    
    async def start_monitoring(self):
        """Start system performance monitoring."""
        if self._monitoring_active:
            logger.warning("Performance monitoring already active")
            return
        
        self._monitoring_active = True
        self._system_monitor_task = asyncio.create_task(self._system_monitor_loop())
        logger.info("Performance monitoring started")
    
    async def stop_monitoring(self):
        """Stop system performance monitoring."""
        if not self._monitoring_active:
            return
        
        self._monitoring_active = False
        
        if self._system_monitor_task:
            self._system_monitor_task.cancel()
            try:
                await self._system_monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Performance monitoring stopped")
    
    async def _system_monitor_loop(self):
        """Main system monitoring loop."""
        while self._monitoring_active:
            try:
                await self._collect_system_metrics()
                await asyncio.sleep(self.system_metric_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in system monitoring: {e}")
                await asyncio.sleep(5)  # Brief pause before retry
    
    async def _collect_system_metrics(self):
        """Collect system performance metrics."""
        try:
            # Get current process
            process = psutil.Process()
            
            # CPU and memory
            cpu_percent = process.cpu_percent()
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()
            
            # System-wide metrics
            system_memory = psutil.virtual_memory()
            disk_usage = psutil.disk_usage('/')
            
            # Network and disk I/O
            disk_io = psutil.disk_io_counters() or type('obj', (object,), {
                'read_bytes': 0, 'write_bytes': 0
            })()
            
            net_io = psutil.net_io_counters() or type('obj', (object,), {
                'bytes_sent': 0, 'bytes_recv': 0
            })()
            
            # Connection count (approximate)
            try:
                connections = len(psutil.net_connections())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                connections = 0
            
            # Thread and process counts
            thread_count = process.num_threads()
            process_count = len(psutil.pids())
            
            # Load average (Unix only)
            load_average = None
            try:
                load_average = list(psutil.getloadavg())
            except (AttributeError, OSError):
                pass  # Not available on Windows
            
            # Create system metrics
            metrics = SystemMetrics(
                timestamp=datetime.utcnow(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_available=system_memory.available,
                memory_used=memory_info.rss,
                disk_usage_percent=disk_usage.percent,
                disk_io_read_bytes=disk_io.read_bytes,
                disk_io_write_bytes=disk_io.write_bytes,
                network_io_bytes_sent=net_io.bytes_sent,
                network_io_bytes_recv=net_io.bytes_recv,
                active_connections=connections,
                thread_count=thread_count,
                process_count=process_count,
                load_average=load_average,
            )
            
            # Store metrics
            with self._lock:
                self.system_metrics.append(metrics)
                self._cleanup_old_metrics()
            
            # Update Prometheus metrics
            MetricsCollector.set_memory_usage("rss", memory_info.rss)
            MetricsCollector.set_memory_usage("vms", memory_info.vms)
            
            # Check thresholds and warn if needed
            self._check_performance_thresholds(metrics)
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
    
    def _check_performance_thresholds(self, metrics: SystemMetrics):
        """Check if performance metrics exceed warning thresholds."""
        if metrics.memory_percent > self.memory_warning_threshold:
            logger.warning(
                f"High memory usage: {metrics.memory_percent:.1%}",
                extra={"memory_percent": metrics.memory_percent}
            )
        
        if metrics.cpu_percent > self.cpu_warning_threshold:
            logger.warning(
                f"High CPU usage: {metrics.cpu_percent:.1f}%",
                extra={"cpu_percent": metrics.cpu_percent}
            )
        
        if metrics.disk_usage_percent > 90:
            logger.warning(
                f"High disk usage: {metrics.disk_usage_percent:.1f}%",
                extra={"disk_usage_percent": metrics.disk_usage_percent}
            )
    
    def _cleanup_old_metrics(self):
        """Remove old metrics beyond retention period."""
        cutoff = datetime.utcnow() - timedelta(hours=self.metric_retention_hours)
        
        # Clean performance metrics
        while self.performance_metrics and self.performance_metrics[0].start_time < cutoff.timestamp():
            self.performance_metrics.popleft()
        
        # Clean system metrics
        while self.system_metrics and self.system_metrics[0].timestamp < cutoff:
            self.system_metrics.popleft()
    
    @contextmanager
    def measure_performance(
        self, 
        name: str, 
        context: Optional[Dict[str, Any]] = None,
        enable_profiling: bool = False
    ) -> Generator[None, None, None]:
        """Context manager to measure performance of code blocks."""
        # Get memory before
        process = psutil.Process()
        memory_before = process.memory_info().rss
        
        start_time = time.time()
        correlation_id = get_correlation_id()
        
        profiler_context = None
        if enable_profiling:
            profiler_context = self.profiler.profile(name, context)
            profiler_context.__enter__()
        
        try:
            yield
        finally:
            end_time = time.time()
            duration = end_time - start_time
            
            # Get memory after
            memory_after = process.memory_info().rss
            memory_delta = memory_after - memory_before
            
            # Create performance metric
            metric = PerformanceMetric(
                name=name,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                memory_before=memory_before,
                memory_after=memory_after,
                memory_delta=memory_delta,
                correlation_id=correlation_id,
                context=context or {}
            )
            
            # Store metric
            with self._lock:
                self.performance_metrics.append(metric)
            
            # Check for slow operations
            if duration > self.slow_query_threshold:
                self._record_slow_operation(metric)
            
            # Log performance info
            logger.debug(
                f"Performance: {name} took {duration:.4f}s",
                extra={
                    "performance_name": name,
                    "duration_ms": metric.duration_ms,
                    "memory_delta": memory_delta,
                    "correlation_id": correlation_id,
                }
            )
            
            # Exit profiler if used
            if profiler_context:
                profiler_context.__exit__(None, None, None)
    
    def _record_slow_operation(self, metric: PerformanceMetric):
        """Record slow operation for analysis."""
        slow_op = {
            "name": metric.name,
            "duration": metric.duration,
            "timestamp": datetime.utcfromtimestamp(metric.start_time),
            "correlation_id": metric.correlation_id,
            "context": metric.context,
        }
        
        with self._lock:
            self.slow_queries.append(slow_op)
        
        logger.warning(
            f"Slow operation detected: {metric.name} took {metric.duration:.4f}s",
            extra=slow_op
        )
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for monitoring."""
        with self._lock:
            # Calculate statistics from recent metrics
            recent_metrics = list(self.performance_metrics)[-1000:]  # Last 1000 operations
            
            if not recent_metrics:
                return {"message": "No performance data available"}
            
            durations = [m.duration for m in recent_metrics]
            memory_deltas = [m.memory_delta for m in recent_metrics]
            
            # Group by operation name
            by_operation = defaultdict(list)
            for metric in recent_metrics:
                by_operation[metric.name].append(metric.duration)
            
            operation_stats = {}
            for name, durations_list in by_operation.items():
                if durations_list:
                    operation_stats[name] = {
                        "count": len(durations_list),
                        "avg_duration": sum(durations_list) / len(durations_list),
                        "min_duration": min(durations_list),
                        "max_duration": max(durations_list),
                    }
            
            return {
                "total_operations": len(recent_metrics),
                "avg_duration": sum(durations) / len(durations) if durations else 0,
                "min_duration": min(durations) if durations else 0,
                "max_duration": max(durations) if durations else 0,
                "avg_memory_delta": sum(memory_deltas) / len(memory_deltas) if memory_deltas else 0,
                "slow_operations_count": len(self.slow_queries),
                "operation_breakdown": operation_stats,
                "system_metrics_count": len(self.system_metrics),
            }
    
    def get_system_metrics(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent system metrics."""
        with self._lock:
            return [m.to_dict() for m in list(self.system_metrics)[-limit:]]
    
    def get_slow_operations(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent slow operations."""
        with self._lock:
            return list(self.slow_queries)[-limit:]


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    return performance_monitor


def performance_timer(name: str, context: Optional[Dict[str, Any]] = None):
    """Decorator to measure function performance."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with performance_monitor.measure_performance(name, context):
                return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            with performance_monitor.measure_performance(name, context):
                return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


@contextmanager
def measure_time(name: str, context: Optional[Dict[str, Any]] = None):
    """Simple context manager to measure execution time."""
    with performance_monitor.measure_performance(name, context):
        yield


@contextmanager
def profile_code(name: str, context: Optional[Dict[str, Any]] = None):
    """Context manager for detailed code profiling."""
    with performance_monitor.measure_performance(name, context, enable_profiling=True):
        yield