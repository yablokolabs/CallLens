"""Asynchronous job processing.

Call analysis can take minutes — it must never be tied to an HTTP request
lifetime. This module defines a small queue abstraction: a lightweight
in-process implementation for local development plus an interface that
Redis/SQS/Celery adapters can implement for production.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Protocol

logger = logging.getLogger(__name__)


class JobQueue(Protocol):
    """Submit and await background analysis jobs."""

    async def submit(self, job_id: str, fn: Callable[[], Awaitable[None]]) -> None:
        """Schedule ``fn`` under ``job_id`` without blocking the caller."""
        ...


class LocalJobQueue:
    """In-process asyncio task queue (local development, single worker)."""

    def __init__(self, max_concurrency: int = 4) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._tasks: dict[str, asyncio.Task] = {}

    async def submit(self, job_id: str, fn: Callable[[], Awaitable[None]]) -> None:
        async def _run() -> None:
            try:
                async with self._semaphore:
                    await fn()
            except Exception:  # noqa: BLE001 - job errors are recorded by the caller
                logger.exception("background job %s failed", job_id)

        self._tasks[job_id] = asyncio.create_task(_run())

    async def wait(self, job_id: str, timeout: float | None = None) -> None:
        task = self._tasks.get(job_id)
        if task is None:
            return
        await asyncio.wait_for(task, timeout=timeout)
