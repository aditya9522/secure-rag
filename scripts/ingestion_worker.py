"""Run durable document-ingestion jobs from PostgreSQL."""

import asyncio
import logging
import os
from datetime import UTC, datetime

from sqlalchemy import select, text

from app.core import runtime
from app.db import SessionLocal
from app.db_models import IngestionJob, Membership, MembershipStatus, OrganizationRole, User
from app.models import Principal
from app.services.document_service import IngestionJobNotClaimed, process_ingestion_job

logger = logging.getLogger(__name__)


async def run_once() -> bool:
    if runtime.openai_provider is None or runtime.pinecone_provider is None:
        raise RuntimeError("Providers are not configured")
    async with SessionLocal() as db:
        await db.execute(text("SELECT set_config('app.is_system_admin', 'true', true)"))
        now = datetime.now(UTC)
        result = await db.execute(
            select(IngestionJob, User, Membership)
            .join(User, User.id == IngestionJob.requested_by)
            .join(
                Membership,
                (Membership.user_id == User.id)
                & (Membership.organization_id == IngestionJob.organization_id),
            )
            .where(
                IngestionJob.available_at <= now,
                (
                    (IngestionJob.status == "queued")
                    | ((IngestionJob.status == "running") & (IngestionJob.locked_until < now))
                ),
                Membership.status == MembershipStatus.active.value,
                User.is_active.is_(True),
            )
            .order_by(IngestionJob.created_at)
            .limit(1)
        )
        row = result.first()
        if row is None:
            return False
        job, user, membership = row
        principal = Principal(
            user_id=str(user.id),
            tenant_id=str(job.organization_id),
            groups=membership.groups or [],
            classification_max=membership.classification_max,
            can_manage_access=membership.role
            in {OrganizationRole.owner.value, OrganizationRole.admin.value},
        )
        try:
            await process_ingestion_job(
                db,
                job.id,
                principal,
                runtime.openai_provider,
                runtime.pinecone_provider,
                runtime.run_provider_operation,
            )
        except IngestionJobNotClaimed:
            return True
        except Exception as exc:  # noqa: BLE001 - job state is persisted by the service
            logger.error(
                "ingestion_worker_job_failed job_id=%s type=%s", job.id, type(exc).__name__
            )
        return True


async def worker() -> None:
    once = os.getenv("INGESTION_WORKER_ONCE", "false").lower() == "true"
    while True:
        processed = await run_once()
        if once or not processed:
            return
        await asyncio.sleep(2)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(worker())
