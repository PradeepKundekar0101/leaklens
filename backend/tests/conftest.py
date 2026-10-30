"""Test configuration. DB tests run against a separate database (TEST_DATABASE_URL, default leaklens_test)."""

import getpass
import os

_user = getpass.getuser()
TEST_DB = os.environ.get("TEST_DATABASE_URL", f"postgresql+psycopg://{_user}@localhost:5432/leaklens_test")
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = TEST_DB
os.environ["DATABASE_URL_DIRECT"] = TEST_DB.replace("+psycopg", "")
os.environ["RUN_WORKER"] = "false"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["VOYAGE_API_KEY"] = ""
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["COOKIE_SECURE"] = "false"
os.environ.setdefault("LOCAL_STORAGE_DIR", "/tmp/leaklens-test-storage")

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402


def _migrate() -> None:
    from alembic.config import Config

    from alembic import command

    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def migrated() -> None:
    _migrate()


@pytest_asyncio.fixture(scope="session")
async def users(migrated) -> dict:
    from sqlalchemy import select

    from app.core.security import hash_password
    from app.db.models import ROLES, User
    from app.db.session import session_scope

    out = {}
    async with session_scope() as s:
        for role in ROLES:
            email = f"{role}@test.local"
            u = (await s.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if u is None:
                u = User(email=email, name=f"Test {role}", role=role, password_hash=hash_password("pw-" + role))
                s.add(u)
            await s.flush()
            out[role] = {"id": u.id, "email": email, "password": "pw-" + role}
        await s.commit()
    return out


@pytest_asyncio.fixture(scope="session")
async def app(migrated):
    from app.agents import runtime
    from app.main import create_app

    await runtime.startup()
    application = create_app()
    yield application
    await runtime.shutdown()


@pytest_asyncio.fixture
async def client(app) -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def login(client: AsyncClient, user: dict) -> AsyncClient:
    r = await client.post("/api/v1/auth/login", json={"email": user["email"], "password": user["password"]})
    assert r.status_code == 200, r.text
    return client


@pytest_asyncio.fixture(scope="session")
async def seeded(app, users):
    from tests.test_graph import _seed

    await _seed()
    return True
