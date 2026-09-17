import asyncio
import io
from types import SimpleNamespace
from uuid import uuid4
from zipfile import ZipFile

import pytest
from fastapi import HTTPException

from app.api.documents import (
    _activate_record_if_indexing,
    _validate_idempotency_key,
    revoke_document,
)
from app.ingest import ingest_document, validate_source_uri
from app.models import Classification, Principal
from app.services.document_service import document_snapshot, fail_or_requeue_ingestion_job


class FakeProvider:
    def __init__(self, embeddings):
        self.embeddings = embeddings

    def embed(self, chunks):
        return self.embeddings


class FakePinecone:
    def __init__(self):
        self.records = None
        self.activated = False
        self.activated_ids = None

    def upsert(self, tenant_id, records):
        self.records = records

    def activate_document(self, tenant_id, document_id, record_ids):
        self.activated = True
        self.activated_ids = record_ids


class FailingPinecone(FakePinecone):
    def __init__(self):
        super().__init__()
        self.deleted = None

    def upsert(self, tenant_id, records):
        self.records = records
        raise RuntimeError("second batch failed")

    def delete_document(self, tenant_id, document_id, record_ids=None):
        self.deleted = (tenant_id, document_id, record_ids)


class FakeSession:
    def __init__(self, rowcount):
        self.rowcount = rowcount
        self.committed = False
        self.rolled_back = False

    async def execute(self, statement):
        return SimpleNamespace(rowcount=self.rowcount)

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True

    def add(self, _value):
        pass


class RevokedDocumentSession:
    def __init__(self, document):
        self.document = document

    async def scalar(self, _statement):
        return self.document


def test_document_activation_is_conditional_on_indexing_state():
    session = FakeSession(rowcount=0)

    activated = asyncio.run(_activate_record_if_indexing(session, uuid4(), uuid4()))

    assert activated is False
    assert session.rolled_back is True
    assert session.committed is False


def test_idempotency_key_is_bounded_and_rejects_control_values():
    assert _validate_idempotency_key(" retry-123 ") == "retry-123"
    with pytest.raises(HTTPException):
        _validate_idempotency_key("\n")
    with pytest.raises(HTTPException):
        _validate_idempotency_key("x" * 129)


def test_document_activation_commits_an_indexing_record():
    session = FakeSession(rowcount=1)

    activated = asyncio.run(_activate_record_if_indexing(session, uuid4(), uuid4()))

    assert activated is True
    assert session.committed is True
    assert session.rolled_back is False


def test_ingest_rejects_incomplete_embedding_response():
    provider = FakeProvider([])
    pinecone = FakePinecone()
    principal = Principal(user_id="u1", tenant_id="tenant-a", groups=["engineering"])

    try:
        ingest_document(
            principal=principal,
            filename="notes.txt",
            content=b"hello world",
            classification=Classification.internal,
            allowed_groups=["engineering"],
            source_uri=None,
            provider=provider,
            pinecone=pinecone,
        )
    except RuntimeError as exc:
        assert "incomplete" in str(exc)
    else:
        raise AssertionError("Expected incomplete embeddings to be rejected")
    assert pinecone.records is None


def test_ingest_cannot_grant_access_to_another_group():
    principal = Principal(user_id="u1", tenant_id="tenant-a", groups=["engineering"])

    try:
        ingest_document(
            principal=principal,
            filename="notes.txt",
            content=b"hello world",
            classification=Classification.internal,
            allowed_groups=["finance"],
            source_uri=None,
            provider=FakeProvider([[0.0] * 1536]),
            pinecone=FakePinecone(),
        )
    except PermissionError as exc:
        assert "outside its own scope" in str(exc)
    else:
        raise AssertionError("Expected out-of-scope group grant to be rejected")


def test_ingest_stages_vectors_as_inactive_until_activation():
    principal = Principal(user_id="u1", tenant_id="tenant-a", groups=["engineering"])
    pinecone = FakePinecone()

    result = ingest_document(
        principal=principal,
        filename="notes.txt",
        content=b"hello world",
        classification=Classification.internal,
        allowed_groups=["engineering"],
        source_uri=None,
        provider=FakeProvider([[0.0] * 1536]),
        pinecone=pinecone,
        activate=False,
    )

    assert result["chunks_indexed"] == 1
    assert pinecone.activated is False
    assert pinecone.records and all(not record["metadata"]["active"] for record in pinecone.records)


def test_ingest_activates_only_the_document_vectors():
    principal = Principal(user_id="u1", tenant_id="tenant-a", groups=["engineering"])
    pinecone = FakePinecone()

    result = ingest_document(
        principal=principal,
        filename="notes.txt",
        content=b"hello world",
        classification=Classification.internal,
        allowed_groups=["engineering"],
        source_uri=None,
        provider=FakeProvider([[0.0] * 1536]),
        pinecone=pinecone,
    )

    assert pinecone.activated is True
    assert pinecone.activated_ids == [f"{result['document_id']}:v1:0"]


def test_ingest_uses_document_version_in_vector_ids_and_metadata():
    principal = Principal(user_id="u1", tenant_id="tenant-a", groups=["engineering"])
    pinecone = FakePinecone()

    result = ingest_document(
        principal=principal,
        filename="notes.txt",
        content=b"hello world",
        classification=Classification.internal,
        allowed_groups=["engineering"],
        source_uri=None,
        provider=FakeProvider([[0.0] * 1536]),
        pinecone=pinecone,
        document_id="doc-1",
        version=2,
        activate=False,
    )

    assert result["_record_ids"] == ["doc-1:v2:0"]
    assert pinecone.records[0]["metadata"]["version"] == 2


def test_source_uri_validation_rejects_embedded_credentials():
    with pytest.raises(ValueError, match="without embedded credentials"):
        validate_source_uri("https://user:password@example.com/source")


def test_revoking_an_already_revoked_document_is_idempotent():
    organization_id = uuid4()
    document_id = uuid4()
    session = RevokedDocumentSession(SimpleNamespace(status="revoked"))
    principal = Principal(user_id=str(uuid4()), tenant_id=str(organization_id))

    response = asyncio.run(revoke_document(document_id, (principal, session, None)))

    assert response.status_code == 204


def test_failed_reindex_restores_the_last_active_document_snapshot():
    owner_id = uuid4()
    record = SimpleNamespace(
        id=uuid4(),
        owner_user_id=owner_id,
        title="current.txt",
        classification=Classification.internal.value,
        allowed_groups=["engineering"],
        source_uri=None,
        source_hash="old-hash",
        version=1,
        status="active",
        chunks_indexed=3,
        organization_id=uuid4(),
        updated_at=None,
    )
    snapshot = document_snapshot(record)
    record.title = "replacement.txt"
    record.version = 2
    record.status = "indexing"
    record.chunks_indexed = 0
    job = SimpleNamespace(
        id=uuid4(),
        attempts=3,
        previous_document=snapshot,
        status="running",
        content=b"replacement",
        locked_until=None,
        last_error=None,
        updated_at=None,
    )
    session = FakeSession(rowcount=1)

    asyncio.run(
        fail_or_requeue_ingestion_job(
            session, job, record, RuntimeError("provider unavailable"), terminal=True
        )
    )

    assert record.status == "active"
    assert record.title == "current.txt"
    assert record.version == 1
    assert record.chunks_indexed == 3
    assert job.previous_document is None
    assert job.status == "failed"
    assert session.committed is True


def test_ingest_defaults_empty_access_groups_to_the_organization():
    principal = Principal(user_id="u1", tenant_id="tenant-a", groups=["owners"])
    pinecone = FakePinecone()

    ingest_document(
        principal=principal,
        filename="notes.txt",
        content=b"hello world",
        classification=Classification.internal,
        allowed_groups=[],
        source_uri=None,
        provider=FakeProvider([[0.0] * 1536]),
        pinecone=pinecone,
        activate=False,
    )

    groups = pinecone.records[0]["metadata"]["allowed_groups"]
    assert "org:tenant-a" in groups


def test_pdf_signature_is_validated_before_parsing():
    from app.ingest import extract_text

    try:
        extract_text("notes.pdf", b"not a pdf")
    except ValueError as exc:
        assert "signature" in str(exc)
    else:
        raise AssertionError("Expected invalid PDF signature to be rejected")


def test_docx_archive_limits_are_checked_before_parser_invocation(monkeypatch):
    from app.config import settings
    from app.ingest import extract_text

    content = io.BytesIO()
    with ZipFile(content, "w") as archive:
        archive.writestr("word/document.xml", b"x" * 32)
    monkeypatch.setattr(settings, "max_archive_uncompressed_bytes", 16)

    with pytest.raises(ValueError, match="expands beyond"):
        extract_text("notes.docx", content.getvalue())


def test_ingest_cleans_staged_vectors_when_upsert_fails():
    principal = Principal(user_id="u1", tenant_id="tenant-a", groups=["engineering"])
    pinecone = FailingPinecone()

    try:
        ingest_document(
            principal=principal,
            filename="notes.txt",
            content=b"hello world",
            classification=Classification.internal,
            allowed_groups=["engineering"],
            source_uri=None,
            provider=FakeProvider([[0.0] * 1536]),
            pinecone=pinecone,
        )
    except RuntimeError as exc:
        assert "staged vectors were cleaned" in str(exc)
    else:
        raise AssertionError("Expected indexing failure")

    assert pinecone.deleted is not None
    assert pinecone.deleted[0] == "tenant-a"
