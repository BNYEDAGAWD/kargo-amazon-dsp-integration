"""Retry logic and resilience utilities."""
import asyncio
import logging
from functools import wraps
from typing import Any, Callable, List, Optional, Type, Union

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_log,
    after_log,
    RetryError,
)
import httpx
import requests

logger = logging.getLogger(__name__)


# Common exceptions that should trigger retries
TRANSIENT_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    httpx.ConnectError,
    httpx.TimeoutException,
    httpx.ReadTimeout,
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ReadTimeout,
)

# HTTP status codes that should trigger retries
RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class RetryableHTTPError(Exception):
    """Custom exception for HTTP errors that should be retried."""
    
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


def should_retry_http_error(exception: Exception) -> bool:
    """Determine if an HTTP error should be retried."""
    if isinstance(exception, RetryableHTTPError):
        return exception.status_code in RETRIABLE_STATUS_CODES
    
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in RETRIABLE_STATUS_CODES
    
    if isinstance(exception, requests.exceptions.HTTPError):
        return exception.response.status_code in RETRIABLE_STATUS_CODES
    
    return False


def retry_on_transient_errors(
    max_attempts: int = 3,
    wait_multiplier: int = 1,
    wait_max: int = 10,
    exceptions: Optional[List[Type[Exception]]] = None,
) -> Callable:
    """
    Decorator for retrying operations on transient errors.
    
    Args:
        max_attempts: Maximum number of retry attempts
        wait_multiplier: Multiplier for exponential backoff
        wait_max: Maximum wait time between retries
        exceptions: Additional exception types to retry on
    """
    retry_exceptions = list(TRANSIENT_EXCEPTIONS)
    if exceptions:
        retry_exceptions.extend(exceptions)
    
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=wait_multiplier, max=wait_max),
        retry=(
            retry_if_exception_type(tuple(retry_exceptions)) |
            retry_if_exception_type(RetryableHTTPError)
        ),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.INFO),
        reraise=True,
    )


def retry_async(
    max_attempts: int = 3,
    wait_multiplier: int = 1,
    wait_max: int = 10,
    exceptions: Optional[List[Type[Exception]]] = None,
) -> Callable:
    """
    Decorator for retrying async operations on transient errors.
    
    Args:
        max_attempts: Maximum number of retry attempts
        wait_multiplier: Multiplier for exponential backoff
        wait_max: Maximum wait time between retries
        exceptions: Additional exception types to retry on
    """
    retry_exceptions = list(TRANSIENT_EXCEPTIONS)
    if exceptions:
        retry_exceptions.extend(exceptions)
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except tuple(retry_exceptions) as e:
                    last_exception = e
                    if attempt == max_attempts - 1:
                        logger.error(
                            f"Max retry attempts ({max_attempts}) reached for {func.__name__}",
                            exc_info=True
                        )
                        raise
                    
                    wait_time = min(wait_multiplier * (2 ** attempt), wait_max)
                    logger.warning(
                        f"Attempt {attempt + 1} failed for {func.__name__}, "
                        f"retrying in {wait_time}s: {str(e)}"
                    )
                    await asyncio.sleep(wait_time)
                except RetryableHTTPError as e:
                    last_exception = e
                    if not should_retry_http_error(e):
                        logger.error(f"Non-retriable HTTP error: {e}")
                        raise
                    
                    if attempt == max_attempts - 1:
                        logger.error(
                            f"Max retry attempts ({max_attempts}) reached for {func.__name__}",
                            exc_info=True
                        )
                        raise
                    
                    wait_time = min(wait_multiplier * (2 ** attempt), wait_max)
                    logger.warning(
                        f"Attempt {attempt + 1} failed for {func.__name__}, "
                        f"retrying in {wait_time}s: {str(e)}"
                    )
                    await asyncio.sleep(wait_time)
                except Exception as e:
                    logger.error(f"Non-retriable error in {func.__name__}: {str(e)}")
                    raise
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


class CircuitBreaker:
    """Simple circuit breaker implementation for external services."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Type[Exception] = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if self.state == "open":
                if self._should_attempt_reset():
                    self.state = "half-open"
                else:
                    raise Exception("Circuit breaker is OPEN")
            
            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise
        
        return wrapper
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt a reset."""
        if self.last_failure_time is None:
            return True
        
        import time
        return (time.time() - self.last_failure_time) >= self.recovery_timeout
    
    def _on_success(self) -> None:
        """Reset the circuit breaker on successful call."""
        self.failure_count = 0
        self.state = "closed"
    
    def _on_failure(self) -> None:
        """Handle failure and potentially open the circuit."""
        import time
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )


# Pre-configured retry decorators for common scenarios
amazon_dsp_retry = retry_on_transient_errors(
    max_attempts=3,
    wait_multiplier=2,
    wait_max=30,
)

kargo_api_retry = retry_on_transient_errors(
    max_attempts=2,
    wait_multiplier=1,
    wait_max=10,
)

database_retry = retry_on_transient_errors(
    max_attempts=3,
    wait_multiplier=1,
    wait_max=5,
)

# Async versions
amazon_dsp_retry_async = retry_async(
    max_attempts=3,
    wait_multiplier=2,
    wait_max=30,
)

kargo_api_retry_async = retry_async(
    max_attempts=2,
    wait_multiplier=1,
    wait_max=10,
)

database_retry_async = retry_async(
    max_attempts=3,
    wait_multiplier=1,
    wait_max=5,
)