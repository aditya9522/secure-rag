import json
import logging
from contextvars import ContextVar

from app.security.policy import inspect_text

logger = logging.getLogger("secure_rag.audit")
request_id_context: ContextVar[str] = ContextVar("request_id", default="")


def redact_for_log(text: str) -> str:
    return inspect_text(text).sanitized_text[:2000]


def audit(event: str, **fields) -> None:
    safe = {k: redact_for_log(str(v)) for k, v in fields.items()}
    safe["event"] = event
    if request_id := request_id_context.get():
        safe["request_id"] = request_id
    # JSON makes event fields searchable without ever logging raw provider
    # responses, bearer tokens, prompts, or database exception text.
    logger.info("%s", json.dumps(safe, sort_keys=True, separators=(",", ":")))


def set_request_id(request_id: str):
    return request_id_context.set(request_id)
