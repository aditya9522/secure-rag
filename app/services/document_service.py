"""Document lifecycle persistence helpers."""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import case, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import audit
from app.config import settings
from app.db_models import (
    AuditEvent,
    DocumentRecord,
    DocumentStatus,
    IngestionJob,
    IngestionJobStatus,
)
from app.ingest import ingest_document
from app.models import Classification, Principal


class IngestionJobNotClaimed(Exception):
    """Another worker owns the job or the job is no longer runnable."""


async def mark_document_failed(
    db: AsyncSession, record: DocumentRecord, principal: Principal, error_type: str
) -> None:
    record.status = DocumentStatus.failed.value
    record.updated_at = datetime.now(UTC)
    db.add(
        AuditEvent(
            organization_id=UUID(principal.tenant_id),
            user_id=UUID(principal.user_id),
            event_type="document_ingest_failed",
            event_metadata={"document_id": str(record.id), "error_type": error_type},
        )
    )
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        logging.getLogger(__name__).exception(
            "document_failure_status_persist_failed tenant_id=%s document_id=%s",
            principal.tenant_id,
            record.id,
        )
        audit(
            "document_failure_status_persist_failed",
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )


async def reconcile_stale_documents(db: AsyncSession) -> list[tuple[str, str]]:
    """Fail closed for uploads abandoned by a crashed request/process.

    Staged vectors are inactive until this state transition completes, so a
    stale record is unavailable to retrieval. The returned tenant/document
    pairs allow the caller to perform best-effort provider cleanup separately.
    """
    cutoff = datetime.now(UTC) - timedelta(minutes=settings.ingestion_stale_after_minutes)
    await db.execute(text("SELECT set_config('app.is_system_admin', 'true', true)"))
    records = (
        await db.scalars(
            select(DocumentRecord).where(
                DocumentRecord.status == DocumentStatus.indexing.value,
                DocumentRecord.updated_at < cutoff,
                ~select(IngestionJob.document_id)
                .where(IngestionJob.document_id == DocumentRecord.id)
                .exists(),
            )
        )
    ).all()
    if not records:
        return []
    stale_pairs = [(str(record.organization_id), str(record.id)) for record in records]
    for record in records:
        record.status = DocumentStatus.failed.value
        record.updated_at = datetime.now(UTC)
        db.add(
            AuditEvent(
                organization_id=record.organization_id,
                user_id=record.owner_user_id,
                event_type="document_ingest_failed",
                event_metadata={"document_id": str(record.id), "error_type": "stale_job"},
            )
        )
    await db.commit()
    return stale_pairs


async def reconcile_expired_ingestion_jobs(db: AsyncSession) -> int:
    """Return expired worker leases to the queue without exposing partial data."""
    now = datetime.now(UTC)
    await db.execute(text("SELECT set_config('app.is_system_admin', 'true', true)"))
    exhausted_document_ids = (
        await db.scalars(
            select(IngestionJob.document_id).where(
                IngestionJob.status == IngestionJobStatus.running.value,
                IngestionJob.locked_until < now,
                IngestionJob.attempts >= settings.ingestion_max_attempts,
            )
        )
    ).all()
    result = await db.execute(
        update(IngestionJob)
        .where(
            IngestionJob.status == IngestionJobStatus.running.value,
            IngestionJob.locked_until < now,
        )
        .values(
            status=case(
                (
                    IngestionJob.attempts >= settings.ingestion_max_attempts,
                    IngestionJobStatus.failed.value,
                ),
                else_=IngestionJobStatus.queued.value,
            ),
            available_at=now,
            locked_until=None,
            updated_at=now,
        )
    )
    if exhausted_document_ids:
        await db.execute(
            update(DocumentRecord)
            .where(
                DocumentRecord.id.in_(exhausted_document_ids),
                DocumentRecord.status == DocumentStatus.indexing.value,
            )
            .values(status=DocumentStatus.failed.value, updated_at=now)
        )
    if result.rowcount:
        await db.commit()
    return result.rowcount or 0


async def activate_record_if_indexing(
    db: AsyncSession, document_id: UUID, organization_id: UUID
) -> bool:
    """Atomically publish a document only if it was not revoked meanwhile."""
    transition = await db.execute(
        update(DocumentRecord)
        .where(
            DocumentRecord.id == document_id,
            DocumentRecord.organization_id == organization_id,
            DocumentRecord.status == DocumentStatus.indexing.value,
        )
        .values(status=DocumentStatus.active.value, updated_at=datetime.now(UTC))
    )
    if transition.rowcount != 1:
        await db.rollback()
        return False
    await db.commit()
    return True


async def claim_ingestion_job(
    db: AsyncSession, job_id: UUID, organization_id: UUID | None = None
) -> IngestionJob:
    """Claim a queued or expired job with a database-serialized lease."""
    if organization_id is not None:
        await db.execute(
            text(
                """
                SELECT set_config('app.current_organization_id', :organization_id, true),
                       set_config('app.is_system_admin', 'false', true)
                """
            ),
            {"organization_id": str(organization_id)},
        )
    now = datetime.now(UTC)
    lease_until = now + timedelta(seconds=settings.ingestion_lease_seconds)
    result = await db.execute(
        update(IngestionJob)
        .where(
            IngestionJob.id == job_id,
            IngestionJob.available_at <= now,
            IngestionJob.attempts < settings.ingestion_max_attempts,
            (
                (IngestionJob.status == IngestionJobStatus.queued.value)
                | (
                    (IngestionJob.status == IngestionJobStatus.running.value)
                    & (IngestionJob.locked_until < now)
                )
            ),
        )
        .values(
            status=IngestionJobStatus.running.value,
            attempts=IngestionJob.attempts + 1,
            locked_until=lease_until,
            updated_at=now,
        )
    )
    if result.rowcount != 1:
        await db.rollback()
        raise IngestionJobNotClaimed
    await db.commit()
    job = await db.get(IngestionJob, job_id)
    if job is None:
        raise IngestionJobNotClaimed
    return job


async def _finish_ingestion_job(
    db: AsyncSession, job: IngestionJob, record: DocumentRecord, result: dict
) -> None:
    record.chunks_indexed = result["chunks_indexed"]
    record.updated_at = datetime.now(UTC)
    job.status = IngestionJobStatus.succeeded.value
    job.content = None
    job.locked_until = None
    job.last_error = None
    job.updated_at = datetime.now(UTC)
    await db.commit()


async def fail_or_requeue_ingestion_job(
    db: AsyncSession,
    job: IngestionJob,
    record: DocumentRecord,
    error: Exception,
    *,
    terminal: bool = False,
) -> None:
    now = datetime.now(UTC)
    exhausted = job.attempts >= settings.ingestion_max_attempts
    if terminal or exhausted:
        if record.status != DocumentStatus.revoked.value:
            record.status = DocumentStatus.failed.value
        job.status = IngestionJobStatus.failed.value
        job.content = None
        job.locked_until = None
    else:
        job.status = IngestionJobStatus.queued.value
        job.available_at = now + timedelta(
            seconds=settings.ingestion_retry_backoff_seconds * (2 ** (job.attempts - 1))
        )
        job.locked_until = None
    record.updated_at = now
    job.last_error = type(error).__name__[:120]
    job.updated_at = now
    db.add(
        AuditEvent(
            organization_id=record.organization_id,
            user_id=record.owner_user_id,
            event_type="document_ingest_failed"
            if terminal or exhausted
            else "ingest_retry_scheduled",
            event_metadata={
                "document_id": str(record.id),
                "job_id": str(job.id),
                "error_type": type(error).__name__,
                "attempt": job.attempts,
            },
        )
    )
    await db.commit()


async def process_ingestion_job(
    db: AsyncSession,
    job_id: UUID,
    principal: Principal,
    provider,
    pinecone,
    run_provider_operation,
) -> dict:
    """Run one leased ingestion job and persist every terminal/intermediate state."""
    job = await claim_ingestion_job(db, job_id, UUID(principal.tenant_id))
    await db.execute(
        text(
            """
            SELECT set_config('app.current_user_id', :user_id, true),
                   set_config('app.current_organization_id', :organization_id, true),
                   set_config('app.is_system_admin', 'false', true)
            """
        ),
        {"user_id": principal.user_id, "organization_id": principal.tenant_id},
    )
    record = await db.get(DocumentRecord, job.document_id)
    if record is None:
        job.status = IngestionJobStatus.failed.value
        job.content = None
        job.locked_until = None
        job.last_error = "DocumentNotFound"
        job.updated_at = datetime.now(UTC)
        await db.commit()
        raise ValueError("Ingestion job document is unavailable")
    if record.status != DocumentStatus.indexing.value or job.content is None:
        error = ValueError("Ingestion job payload is unavailable")
        if record.status == DocumentStatus.indexing.value:
            await fail_or_requeue_ingestion_job(db, job, record, error, terminal=True)
        else:
            job.status = IngestionJobStatus.failed.value
            job.content = None
            job.locked_until = None
            job.last_error = type(error).__name__
            job.updated_at = datetime.now(UTC)
            await db.commit()
        raise error
    try:
        result = await run_provider_operation(
            ingest_document,
            principal=principal,
            filename=job.filename,
            content=job.content,
            classification=Classification(job.classification),
            allowed_groups=job.allowed_groups or [],
            source_uri=job.source_uri,
            provider=provider,
            pinecone=pinecone,
            document_id=str(job.document_id),
            version=record.version,
            activate=False,
        )
        await run_provider_operation(
            pinecone.activate_document,
            str(job.organization_id),
            str(job.document_id),
            result["_record_ids"],
        )
        activated = await activate_record_if_indexing(db, job.document_id, job.organization_id)
        if not activated:
            await run_provider_operation(
                pinecone.delete_document, str(job.organization_id), str(job.document_id)
            )
            await fail_or_requeue_ingestion_job(
                db, job, record, ValueError("Document was revoked during activation"), terminal=True
            )
            raise IngestionJobNotClaimed
        await _finish_ingestion_job(db, job, record, result)
        return result
    except (PermissionError, ValueError) as exc:
        await fail_or_requeue_ingestion_job(db, job, record, exc, terminal=True)
        raise
    except IngestionJobNotClaimed:
        raise
    except Exception as exc:
        if job.attempts >= settings.ingestion_max_attempts:
            try:
                await run_provider_operation(
                    pinecone.delete_document, str(job.organization_id), str(job.document_id)
                )
            except Exception as cleanup_exc:  # noqa: BLE001 - terminal state remains fail-closed
                logging.getLogger(__name__).error(
                    "ingestion_terminal_cleanup_failed job_id=%s type=%s",
                    job.id,
                    type(cleanup_exc).__name__,
                )
        await fail_or_requeue_ingestion_job(db, job, record, exc)
        raise
