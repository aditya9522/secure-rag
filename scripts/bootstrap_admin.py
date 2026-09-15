"""Promote an existing account to system administrator after manual approval."""

import asyncio
import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.db_models import User


async def main(email: str) -> None:
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == email.strip().lower()))
        if not user:
            raise SystemExit("No account found for that email")
        user.is_system_admin = True
        await session.commit()
        print(f"System administrator enabled for {user.email}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/bootstrap_admin.py admin@example.com")
    asyncio.run(main(sys.argv[1]))
