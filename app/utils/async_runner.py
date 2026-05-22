"""Run async coroutines from sync contexts using a dedicated thread.

Streamlit runs on an asyncio event loop (Uvicorn), which prevents
asyncio.run() from being called directly.  nest-asyncio patches break
Python 3.14 compatibility (anyio + weakref crash).  This module
provides a thread-based bridge that works across all Python versions
without patching the global event loop.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from typing import Any


def run_async(coro: Any, /, timeout: float | None = None) -> Any:
    """Execute an async coroutine and return its result synchronously.

    Creates a dedicated OS thread with its own asyncio event loop,
    runs the coroutine to completion there, and returns the result to
    the caller.  This avoids the "cannot be called from a running
    event loop" restriction of ``asyncio.run()`` without patching the
    global event loop (unlike ``nest-asyncio``).

    Args:
        coro: An async coroutine object.
        timeout: Optional timeout in seconds.  If the coroutine does
            not complete within this time, a TimeoutError is raised.

    Returns:
        The value returned by the coroutine.

    Raises:
        concurrent.futures.TimeoutError: If *timeout* is exceeded.
        Any exception raised by the coroutine is re-raised.
    """
    future: concurrent.futures.Future[T] = concurrent.futures.Future()

    def _target() -> None:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(coro)  # type: ignore[arg-type]
            future.set_result(result)
        except Exception as exc:
            future.set_exception(exc)
        finally:
            loop.close()

    thread = threading.Thread(target=_target, daemon=True, name="async-runner")
    thread.start()
    thread_result = future.result(timeout=timeout)
    thread.join(timeout=1)
    return thread_result
