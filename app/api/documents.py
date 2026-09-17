"""Knowledge-source listing, ingestion, and revocation routes."""

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    authorized_principal_dep,
    org_admin_dep,
    principal_uuid,
    read_upload_bounded,
)
from app.audit import audit
from app.config import settings
from app.core import runtime
from app.db import get_db
from app.db_models import (
    AuditEvent,
    DocumentRecord,
    DocumentStatus,
    IngestionJob,
    IngestionJobStatus,
    Membership,
)
from app.ingest import ingest_document, validate_source_uri
from app.models import Classification, DocumentSummary, IngestResponse, Principal
from app.security.policy import can_view_document
from app.services.document_service import (
    activate_record_if_indexing as _activate_record_if_indexing,
)
from app.services.document_service import (
    claim_ingestion_job,
    document_snapshot,
    fail_or_requeue_ingestion_job,
)

router = APIRouter(prefix="/v1/documents", tags=["documents"])


def _validate_idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value or len(value) > 128 or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise HTTPException(
            400, "Idempotency-Key must be a non-empty value of at most 128 characters"
        )
    return value


def _replayed_ingest_response(document: DocumentRecord) -> dict:
    return {
        "document_id": str(document.id),
        "chunks_indexed": document.chunks_indexed,
        "classification": Classification(document.classification),
        "source_uri": document.source_uri,
        "provenance": {"sha256": document.source_hash, "version": document.version},
    }


@router.get("", response_model=list[DocumentSummary])
async def list_documents(
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0, le=1_000_000),
    principal: Principal = Depends(authorized_principal_dep),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    organization_id = UUID(principal.tenant_id)
    conditions = [DocumentRecord.organization_id == organization_id]
    if not principal.can_manage_access:
        principal_groups = list(
            dict.fromkeys(
                principal.groups + [f"org:{principal.tenant_id}", f"user:{principal.user_id}"]
            )
        )
        conditions.extend(
            [
                DocumentRecord.status == DocumentStatus.active.value,
                DocumentRecord.classification.in_(
                    classification.value
                    for classification in Classification
                    if principal.can_read_classification(classification)
                ),
                DocumentRecord.allowed_groups.op("?|")(principal_groups),
            ]
        )
    result = await db.execute(
        select(DocumentRecord, IngestionJob.last_error)
        .outerjoin(IngestionJob, IngestionJob.document_id == DocumentRecord.id)
        .where(*conditions)
        .order_by(DocumentRecord.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return [
        {
            "id": document.id,
            "title": document.title,
            "classification": document.classification,
            "allowed_groups": document.allowed_groups or [],
            "source_uri": document.source_uri,
            "status": document.status,
            "chunks_indexed": document.chunks_indexed,
            "created_at": document.created_at,
            "updated_at": document.updated_at,
            "last_error": last_error,
            "can_retry": document.status == DocumentStatus.failed.value,
        }
        for document, last_error in result.all()
        if can_view_document(
            status=document.status,
            classification=document.classification,
            allowed_groups=document.allowed_groups or [],
            principal=principal,
        )
    ]


@router.delete("/{document_id}", status_code=204)
async def revoke_document(
    document_id: UUID,
    auth: tuple[Principal, AsyncSession, Membership] = Depends(org_admin_dep),
):
    principal, db, _ = auth
    organization_id = UUID(principal.tenant_id)
    document = await db.scalar(
        select(DocumentRecord).where(
            DocumentRecord.id == document_id, DocumentRecord.organization_id == organization_id
        )
    )
    if not document:
        raise HTTPException(404, "Document not found")

    if document.status == DocumentStatus.revoked.value:
        return JSONResponse(status_code=204, content=None)

    document.status = DocumentStatus.revoked.value
    document.updated_at = datetime.now(UTC)
    db.add(
        AuditEvent(
            organization_id=organization_id,
            user_id=principal_uuid(principal),
            event_type="document_revoked",
            event_metadata={"document_id": str(document_id)},
        )
    )
    await db.commit()

    if runtime.pinecone_provider is None:
        raise HTTPException(503, "Retrieval provider is not configured")
    try:
        await runtime.run_provider_operation(
            runtime.pinecone_provider.delete_document, str(organization_id), str(document_id)
        )
    except Exception as exc:
        logging.getLogger(__name__).error(
            "document_revoke_index_update_failed type=%s", type(exc).__name__
        )
        raise HTTPException(503, "Document revocation is temporarily unavailable") from exc
    return JSONResponse(status_code=204, content=None)


@router.post("", response_model=IngestResponse)
@runtime.limiter.limit(f"{max(1, settings.rate_limit_per_minute // 4)}/minute")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
    classification: Classification = Form(Classification.internal),  # noqa: B008
    allowed_groups: str = Form(""),
    source_uri: str | None = Form(None),
    retry_document_id: UUID | None = Form(None),  # noqa: B008
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    auth: tuple[Principal, AsyncSession, Membership] = Depends(org_admin_dep),
):
    principal, db, _ = auth
    idempotency_key = _validate_idempotency_key(idempotency_key)
    if runtime.openai_provider is None or runtime.pinecone_provider is None:
        raise HTTPException(503, "Providers are not configured")
    if not file.filename:
        raise HTTPException(400, "Filename required")
    if len(allowed_groups) > 4096:
        raise HTTPException(400, "Access group list is too large")
    try:
        source_uri = validate_source_uri(source_uri)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    existing = None
    if retry_document_id is not None:
        existing = await db.scalar(
            select(DocumentRecord).where(
                DocumentRecord.id == retry_document_id,
                DocumentRecord.organization_id == UUID(principal.tenant_id),
            )
        )
        if existing is None:
            raise HTTPException(404, "Document not found")
        if existing.status != DocumentStatus.failed.value:
            raise HTTPException(409, "Only failed documents can be retried")
    if idempotency_key:
        existing = await db.scalar(
            select(DocumentRecord).where(
                DocumentRecord.organization_id == UUID(principal.tenant_id),
                DocumentRecord.idempotency_key == idempotency_key,
            )
        )
        if existing and existing.status == DocumentStatus.active.value:
            return _replayed_ingest_response(existing)
        if existing and existing.status == DocumentStatus.indexing.value:
            raise HTTPException(409, "Document ingestion is already in progress")
        if existing and existing.status == DocumentStatus.revoked.value:
            raise HTTPException(409, "The idempotency key belongs to a revoked document")
    content = await read_upload_bounded(file)
    safe_filename = Path(file.filename).name
    if not safe_filename or safe_filename in {".", ".."}:
        raise HTTPException(400, "Filename required")
    groups = [group.strip() for group in allowed_groups.split(",") if group.strip()]
    document_id = existing.id if existing else uuid4()
    stored_groups = sorted(set(groups or [f"org:{principal.tenant_id}"]))
    if f"user:{principal.user_id}" not in stored_groups:
        stored_groups.append(f"user:{principal.user_id}")
    if existing:
        record = existing
        previous_document = (
            document_snapshot(existing) if existing.status == DocumentStatus.active.value else None
        )
        record.owner_user_id = UUID(principal.user_id)
        record.title = safe_filename[:256]
        record.classification = classification.value
        record.allowed_groups = stored_groups
        record.source_uri = source_uri
        record.source_hash = hashlib.sha256(content).hexdigest()
        record.version += 1
        record.status = DocumentStatus.indexing.value
        record.chunks_indexed = 0
        record.updated_at = datetime.now(UTC)
    else:
        record = DocumentRecord(
            id=document_id,
            organization_id=UUID(principal.tenant_id),
            owner_user_id=UUID(principal.user_id),
            title=safe_filename[:256],
            classification=classification.value,
            allowed_groups=stored_groups,
            source_uri=source_uri,
            previous_document=None,
            source_hash=hashlib.sha256(content).hexdigest(),
            idempotency_key=idempotency_key,
            version=1,
            status=DocumentStatus.indexing.value,
            chunks_indexed=0,
        )
        db.add(record)
    job = await db.scalar(select(IngestionJob).where(IngestionJob.document_id == document_id))
    if job is None:
        job = IngestionJob(
            document_id=document_id,
            organization_id=UUID(principal.tenant_id),
            requested_by=UUID(principal.user_id),
            filename=safe_filename,
            content=content,
            classification=classification.value,
            allowed_groups=stored_groups,
            source_uri=source_uri,
            status=IngestionJobStatus.queued.value,
            attempts=0,
            available_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(job)
    else:
        job.requested_by = UUID(principal.user_id)
        job.filename = safe_filename
        job.content = content
        job.classification = classification.value
        job.allowed_groups = stored_groups
        job.source_uri = source_uri
        job.previous_document = previous_document
        job.status = IngestionJobStatus.queued.value
        job.attempts = 0
        job.available_at = datetime.now(UTC)
        job.locked_until = None
        job.last_error = None
        job.updated_at = datetime.now(UTC)
    staged_record_ids: list[str] = []
    try:
        await db.commit()
    except (ValueError, IntegrityError) as exc:
        await db.rollback()
        if idempotency_key:
            duplicate = await db.scalar(
                select(DocumentRecord).where(
                    DocumentRecord.organization_id == UUID(principal.tenant_id),
                    DocumentRecord.idempotency_key == idempotency_key,
                )
            )
            if duplicate:
                raise HTTPException(409, "Document ingestion is already in progress") from exc
        logging.getLogger(__name__).error(
            "document_index_record_create_failed type=%s", type(exc).__name__
        )
        raise HTTPException(503, "Document ingestion could not be started") from exc
    job = await claim_ingestion_job(db, job.id, UUID(principal.tenant_id))
    try:
        result = await runtime.run_provider_operation(
            ingest_document,
            principal=principal,
            filename=safe_filename,
            content=content,
            classification=classification,
            allowed_groups=groups,
            source_uri=source_uri,
            provider=runtime.openai_provider,
            pinecone=runtime.pinecone_provider,
            document_id=str(document_id),
            version=record.version,
            activate=False,
        )
    except PermissionError as exc:
        await fail_or_requeue_ingestion_job(db, job, record, exc, terminal=True)
        audit("ingest_denied", user_id=principal.user_id, tenant_id=principal.tenant_id)
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        await fail_or_requeue_ingestion_job(db, job, record, exc, terminal=True)
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        await fail_or_requeue_ingestion_job(db, job, record, exc)
        audit(
            "ingest_provider_failure",
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            error=type(exc).__name__,
        )
        raise HTTPException(503, "Document ingestion is temporarily unavailable") from exc
    except Exception as exc:
        await fail_or_requeue_ingestion_job(db, job, record, exc)
        audit(
            "ingest_unexpected_failure",
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            error=type(exc).__name__,
        )
        raise HTTPException(503, "Document ingestion is temporarily unavailable") from exc
    staged_record_ids = result["_record_ids"]
    record.chunks_indexed = result["chunks_indexed"]
    record.updated_at = datetime.now(UTC)
    try:
        await db.commit()
        await runtime.run_provider_operation(
            runtime.pinecone_provider.activate_document,
            principal.tenant_id,
            str(document_id),
            result["_record_ids"],
        )
    except Exception as exc:
        await db.rollback()
        await fail_or_requeue_ingestion_job(db, job, record, exc, terminal=True)
        try:
            await runtime.run_provider_operation(
                runtime.pinecone_provider.delete_document,
                principal.tenant_id,
                str(document_id),
                staged_record_ids,
            )
        except Exception:
            logging.getLogger(__name__).exception(
                "document_cleanup_failed tenant_id=%s document_id=%s",
                principal.tenant_id,
                document_id,
            )
        raise HTTPException(503, "Document activation is temporarily unavailable") from exc

    # The conditional UPDATE takes a row lock until commit, so a concurrent
    # revoke either wins before activation (and we clean up) or observes the
    # committed active state and revokes it afterward.
    try:
        activated = await _activate_record_if_indexing(db, document_id, UUID(principal.tenant_id))
    except Exception as exc:
        await db.rollback()
        await fail_or_requeue_ingestion_job(db, job, record, exc, terminal=True)
        try:
            await runtime.run_provider_operation(
                runtime.pinecone_provider.delete_document,
                principal.tenant_id,
                str(document_id),
                staged_record_ids,
            )
        except Exception:
            logging.getLogger(__name__).exception(
                "document_cleanup_failed tenant_id=%s document_id=%s",
                principal.tenant_id,
                document_id,
            )
        raise HTTPException(503, "Document metadata could not be finalized") from exc
    if not activated:
        try:
            await runtime.run_provider_operation(
                runtime.pinecone_provider.delete_document,
                principal.tenant_id,
                str(document_id),
                staged_record_ids,
            )
        except Exception:
            logging.getLogger(__name__).exception(
                "document_cleanup_failed tenant_id=%s document_id=%s",
                principal.tenant_id,
                document_id,
            )
        await fail_or_requeue_ingestion_job(
            db,
            job,
            record,
            RuntimeError("Document was revoked during activation"),
            terminal=True,
        )
        raise HTTPException(409, "Document was revoked during activation")
    previous_version = int(job.previous_document["version"]) if job.previous_document else None
    job.status = IngestionJobStatus.succeeded.value
    job.content = None
    job.locked_until = None
    job.last_error = None
    job.updated_at = datetime.now(UTC)
    await db.commit()
    if previous_version is not None:
        try:
            await runtime.run_provider_operation(
                runtime.pinecone_provider.delete_document,
                principal.tenant_id,
                str(document_id),
                version=previous_version,
            )
        except Exception as exc:  # noqa: BLE001 - old vectors are no longer queryable
            logging.getLogger(__name__).warning(
                "document_previous_version_cleanup_failed document_id=%s type=%s",
                document_id,
                type(exc).__name__,
            )
        job.previous_document = None
        await db.commit()
    audit(
        "document_ingested",
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
        document_id=result["document_id"],
    )
    return result
