"""Auth, role coverage, upload spoofing, read-only tools, jobs."""

import pytest
from fastapi.routing import APIRoute
from sqlalchemy.exc import DBAPIError

from app.core.security import COOKIE_NAME
from tests.conftest import login

PUBLIC = {("GET", "/health"), ("POST", "/api/v1/auth/login"), ("GET", "/api/v1/files/{token}")}


def _role_deps(route: APIRoute) -> list:
    found = []

    def walk(dependant) -> None:
        for d in dependant.dependencies:
            if hasattr(d.call, "required_roles"):
                found.append(d.call.required_roles)
            walk(d)

    walk(route.dependant)
    return found


async def test_every_route_has_a_role_dependency(app):
    missing = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            if (method, route.path) in PUBLIC:
                continue
            if not _role_deps(route):
                missing.append(f"{method} {route.path}")
    assert missing == []


async def test_no_cookie_is_401(client):
    for path in ("/api/v1/claims", "/api/v1/auth/me", "/api/v1/dashboard/summary", "/api/v1/audit"):
        r = await client.get(path)
        assert r.status_code == 401, path
        assert r.json()["error"]["code"] == "unauthorized"


async def test_bad_cookie_is_401(client):
    client.cookies.set(COOKIE_NAME, "not-a-jwt")
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_login_sets_httponly_cookie_and_me(client, users):
    r = await client.post(
        "/api/v1/auth/login", json={"email": users["adjuster"]["email"], "password": users["adjuster"]["password"]}
    )
    assert r.status_code == 200
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    me = await client.get("/api/v1/auth/me")
    assert me.json()["role"] == "adjuster"


async def test_wrong_password(client, users):
    r = await client.post("/api/v1/auth/login", json={"email": users["adjuster"]["email"], "password": "nope"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"


@pytest.mark.parametrize(
    ("role", "method", "path", "body"),
    [
        ("auditor", "POST", "/api/v1/admin/retrain", None),
        ("adjuster", "POST", "/api/v1/admin/process-batch", {"limit": 1}),
        ("adjuster", "GET", "/api/v1/providers", None),
        ("adjuster", "GET", "/api/v1/dashboard/summary", None),
        ("auditor", "POST", "/api/v1/claims/C0000001/review", {"decision": "approve", "final_amount": "1"}),
        ("manager", "POST", "/api/v1/claims/C0000001/review", {"decision": "approve", "final_amount": "1"}),
        ("manager", "POST", "/api/v1/policies/GOLD/params/approve", None),
        ("auditor", "POST", "/api/v1/claims/C0000001/process", None),
    ],
)
async def test_wrong_role_is_403(client, users, role, method, path, body):
    await login(client, users[role])
    r = await client.request(method, path, json=body)
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "forbidden"


async def test_logout_clears_cookie(client, users):
    await login(client, users["manager"])
    r = await client.post("/api/v1/auth/logout")
    assert r.status_code == 200
    assert 'leaklens_session=""' in r.headers["set-cookie"] or "Max-Age=0" in r.headers["set-cookie"]


def test_upload_spoofing_rejected():
    from app.services.documents.validate import UploadRejected, sniff

    with pytest.raises(UploadRejected):
        sniff(b"MZ\x90\x00" + b"\x00" * 100)  # a Windows executable renamed to .pdf
    with pytest.raises(UploadRejected):
        sniff(b"<html><script>alert(1)</script></html>")
    assert sniff(b"%PDF-1.7\n%...")[0] == "application/pdf"
    assert sniff(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)[0] == "image/png"


def test_upload_size_limit():
    from app.services.documents.validate import MAX_BYTES, UploadRejected, sniff

    with pytest.raises(UploadRejected):
        sniff(b"%PDF-" + b"0" * MAX_BYTES)


async def test_readonly_session_rejects_writes(migrated):
    from app.agents.tools.readonly import readonly_check

    with pytest.raises(DBAPIError, match="read-only"):
        await readonly_check()


def test_every_agent_tool_uses_a_readonly_session():
    import inspect

    from app.agents.tools import readonly

    for tool in readonly.COPILOT_TOOLS:
        src = inspect.getsource(tool.fn)
        uses_store = "runtime.store()" in src and ("asearch" in src or "aget" in src)
        assert "readonly_session()" in src or uses_store or "peer_distribution(" in src, tool.name
        for forbidden in ("session_scope", ".add(", ".commit(", "aput(", "adelete("):
            assert forbidden not in src, f"{tool.name} uses {forbidden}"


async def test_job_enqueued_processed_and_done(migrated):
    from app.db.models import Job
    from app.db.session import session_scope
    from app.jobs import handlers  # noqa: F401
    from app.jobs.runner import drain, enqueue

    async with session_scope() as s:
        job = await enqueue(s, "noop", {"hello": "world"})
        await s.commit()
        job_id = job.id
    await drain()
    async with session_scope() as s:
        job = await s.get(Job, job_id)
        assert job.status == "done"
        assert job.result == {"echo": {"hello": "world"}}
        assert job.attempts == 1


async def test_failing_job_retries_then_fails(migrated):
    from app.db.models import Job
    from app.db.session import session_scope
    from app.jobs.runner import HANDLERS, drain, enqueue

    async def boom(payload):
        raise RuntimeError("boom")

    HANDLERS["boom"] = boom
    async with session_scope() as s:
        job = await enqueue(s, "boom", {})
        await s.commit()
        job_id = job.id
    await drain()
    async with session_scope() as s:
        job = await s.get(Job, job_id)
        assert job.status == "failed"
        assert job.attempts == 3
        assert "boom" in job.error
