"""Shared provider runtime and bounded blocking-operation execution."""

import asyncio
import logging

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.providers.openai_provider import OpenAIProvider
from app.providers.pinecone_provider import PineconeProvider
from app.security.auth import decode_principal

provider_operation_limit = asyncio.Semaphore(settings.provider_concurrency_limit)


def rate_limit_key(request: Request) -> str:
    """Use verified tenant/user identity when available, IP otherwise."""
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token:
        try:
            principal = decode_principal(token)
            return f"principal:{principal.tenant_id}:{principal.user_id}"
        except Exception:  # noqa: BLE001 - authentication dependency returns the real error
            return get_remote_address(request)
    return get_remote_address(request)


limiter = Limiter(
    key_func=rate_limit_key,
    default_limits=[f"{settings.rate_limit_per_minute}/minute"],
    storage_uri=settings.rate_limit_storage_uri,
)


async def run_provider_operation(function, *args, **kwargs):
    await provider_operation_limit.acquire()
    operation = asyncio.create_task(run_in_threadpool(function, *args, **kwargs))
    try:
        result = await asyncio.wait_for(
            asyncio.shield(operation), settings.provider_operation_timeout_seconds
        )
    except TimeoutError as exc:
        # A Python worker thread cannot be forcefully cancelled. Keep the
        # bounded-operation slot occupied until the late worker completes so a
        # timeout cannot turn into unbounded concurrency.
        operation.add_done_callback(_release_and_log_late_operation)
        raise RuntimeError("Provider operation timed out") from exc
    except asyncio.CancelledError:
        operation.add_done_callback(_release_and_log_late_operation)
        raise
    except BaseException:
        provider_operation_limit.release()
        raise
    else:
        provider_operation_limit.release()
        return result


def _log_late_operation(operation: asyncio.Future) -> None:
    if operation.cancelled():
        return
    try:
        operation.result()
    except Exception as exc:  # noqa: BLE001 - late failures are diagnostics only
        logging.getLogger(__name__).warning(
            "provider_operation_late_failure type=%s", type(exc).__name__
        )


def _release_and_log_late_operation(operation: asyncio.Future) -> None:
    try:
        _log_late_operation(operation)
    finally:
        provider_operation_limit.release()


try:
    openai_provider = OpenAIProvider()
    pinecone_provider = PineconeProvider()
except Exception as exc:  # noqa: BLE001 - keep liveness available while failing closed
    logging.getLogger(__name__).error("provider_initialization_failed type=%s", type(exc).__name__)
    openai_provider = None
    pinecone_provider = None
