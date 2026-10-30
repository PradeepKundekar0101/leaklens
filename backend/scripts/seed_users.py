"""Create one user per role. Password from SEED_PASSWORD (default for local/demo only)."""

import asyncio
import os

from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import ROLES, User
from app.db.session import dispose_engine, session_scope

DEFAULT_PASSWORD = "LeakLens!2026"  # local/demo seed only; set SEED_PASSWORD elsewhere
NAMES = {"adjuster": "Asha Rao", "auditor": "Vikram Mehta", "manager": "Neha Kapoor", "admin": "Arjun Iyer"}


async def main() -> None:
    password = os.environ.get("SEED_PASSWORD", DEFAULT_PASSWORD)
    async with session_scope() as session:
        for role in ROLES:
            email = f"{role}@leaklens.local"
            user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is None:
                session.add(User(email=email, name=NAMES[role], role=role, password_hash=hash_password(password)))
                print(f"created {email} ({role})")
            else:
                user.password_hash = hash_password(password)
                user.role = role
                print(f"updated {email} ({role})")
        await session.commit()
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
