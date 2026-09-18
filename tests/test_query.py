import asyncio
import json
from uuid import uuid4

import app.api.query as query_api
from app.models import Principal, QueryRequest, QueryResponse


class _ConnectedRequest:
    async def is_disconnected(self):
        return False


class _Database:
    async def rollback(self):
        return None


def test_stream_emits_only_validated_answer(monkeypatch):
    principal = Principal(user_id=str(uuid4()), tenant_id=str(uuid4()))
    final_response = QueryResponse(
        answer="Final **verified** answer",
        citations=[],
        grounded=False,
        mode="conversational",
        policy_flags=["conversational"],
    )

    async def fake_active_document_ids(_db, _principal):
        return {}

    async def fake_persist_query(_db, _principal, _body, _result):
        return uuid4()

    async def fake_run_provider_operation(_function, *_args, **kwargs):
        kwargs["on_delta"]("provisional-untrusted-answer")
        return final_response

    monkeypatch.setattr(query_api, "active_document_ids", fake_active_document_ids)
    monkeypatch.setattr(query_api, "persist_query", fake_persist_query)
    monkeypatch.setattr(query_api.runtime, "openai_provider", object())
    monkeypatch.setattr(query_api.runtime, "pinecone_provider", object())
    monkeypatch.setattr(query_api.runtime, "run_provider_operation", fake_run_provider_operation)

    endpoint = getattr(query_api.query_stream, "__wrapped__", query_api.query_stream)
    response = asyncio.run(
        endpoint(
            _ConnectedRequest(),
            QueryRequest(query="hello"),
            principal,
            _Database(),
        )
    )

    async def collect():
        return [chunk async for chunk in response.body_iterator]

    events = asyncio.run(collect())
    payload = "".join(events)

    assert "provisional-untrusted-answer" not in payload
    assert "Final **verified** answer" in payload
    assert "event: complete" in payload
    complete_data = next(
        line.removeprefix("data: ")
        for line in payload.splitlines()
        if line.startswith("data: ") and "conversation_id" in line
    )
    assert json.loads(complete_data)["response"]["answer"] == final_response.answer
