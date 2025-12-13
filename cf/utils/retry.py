"""
Retry utilities for robust error handling

Provides decorators and utilities for retrying operations with exponential backoff.
"""

import time
import functools
from typing import Callable, Type, Tuple, Any


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator that retries a function with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exceptions: Tuple of exception types to catch and retry

    Returns:
        Decorated function with retry logic

    Example:
        @retry_with_backoff(max_attempts=3, base_delay=1.0)
        def call_llm(prompt):
            return llm.generate(prompt)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts:
                        # Last attempt failed, raise the exception
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)

                    # Log retry attempt if func has a logger
                    if hasattr(args[0] if args else None, 'logger'):
                        logger = args[0].logger
                        logger.warning(
                            f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )

                    time.sleep(delay)

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


def with_fallback(fallback_value: Any = None, log_error: bool = True):
    """
    Decorator that returns a fallback value if function raises an exception.

    Args:
        fallback_value: Value to return on exception
        log_error: Whether to log the error

    Returns:
        Decorated function with fallback logic

    Example:
        @with_fallback(fallback_value={'success': False})
        def risky_operation():
            return perform_operation()
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_error and hasattr(args[0] if args else None, 'logger'):
                    logger = args[0].logger
                    logger.error(f"{func.__name__} failed: {e}. Using fallback value.")
                return fallback_value
        return wrapper
    return decorator
