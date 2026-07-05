"""Retry helper with exponential backoff for flaky/rate-limited network
calls (Instagram connection drops, rate limiting)."""

from __future__ import annotations

import asyncio
import logging
from functools import wraps
from typing import Awaitable, Callable, ParamSpec, TypeVar

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def retry_async(
    exceptions: tuple[type[BaseException], ...],
    attempts: int = 3,
    base_delay: float = 5.0,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Retry an async function up to `attempts` times, doubling the delay
    each time a listed exception is raised. Re-raises the last error once
    attempts are exhausted so the caller can decide how to degrade
    gracefully (e.g. skip one account, never crash the whole bot)."""

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            delay = base_delay
            last_error: BaseException | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_error = exc
                    if attempt == attempts:
                        break
                    logger.warning(
                        "%s başarısız oldu (deneme %s/%s): %s - %.1f sn sonra tekrar denenecek",
                        func.__name__,
                        attempt,
                        attempts,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    delay *= 2

            logger.error("%s tüm denemelerden sonra başarısız oldu: %s", func.__name__, last_error)
            assert last_error is not None
            raise last_error

        return wrapper

    return decorator
