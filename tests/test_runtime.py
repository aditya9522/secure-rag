import asyncio
import threading

import pytest

from app.config import settings
from app.core import runtime


def test_provider_operation_timeout_preserves_concurrency_slot(monkeypatch):
    finished = threading.Event()
    release = threading.Event()

    def blocking_operation():
        release.wait(2)
        finished.set()

    async def exercise():
        monkeypatch.setattr(settings, "provider_operation_timeout_seconds", 0.01)
        with pytest.raises(RuntimeError, match="timed out"):
            await runtime.run_provider_operation(blocking_operation)
        assert not finished.is_set()
        release.set()
        for _ in range(20):
            if finished.is_set():
                return
            await asyncio.sleep(0.01)
        raise AssertionError("late provider worker did not finish")

    asyncio.run(exercise())


def test_provider_operation_releases_concurrency_slot_after_success(monkeypatch):
    async def exercise():
        monkeypatch.setattr(runtime, "provider_operation_limit", asyncio.Semaphore(1))
        monkeypatch.setattr(settings, "provider_operation_timeout_seconds", 10)

        async def immediate_threadpool(function, *args, **kwargs):
            return function(*args, **kwargs)

        monkeypatch.setattr(runtime, "run_in_threadpool", immediate_threadpool)

        assert await runtime.run_provider_operation(lambda: "ok") == "ok"
        assert await asyncio.wait_for(runtime.run_provider_operation(lambda: "again"), 2) == "again"

    asyncio.run(exercise())
