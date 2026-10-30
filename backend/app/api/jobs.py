from typing import Annotated

import jwt
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, not_found
from app.core.security import ANY_ROLE
from app.db.models import Job
from app.db.session import get_session
from app.storage.spaces import LocalStorage, get_storage

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}", dependencies=[Depends(ANY_ROLE)])
async def get_job(job_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    job = await session.get(Job, job_id)
    if job is None:
        raise not_found("Job")
    return {
        "id": job.id,
        "type": job.type,
        "status": job.status,
        "result": job.result,
        "error": job.error,
        "attempts": job.attempts,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }


@router.get("/files/{token}", include_in_schema=False)
async def local_file(token: str) -> Response:
    """Serves local-storage presigned URLs. The signed, 5-minute token is the credential (like an S3 URL)."""
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise not_found("File")
    try:
        key = storage.resolve_token(token)
        data = storage.download(key)
    except (jwt.PyJWTError, FileNotFoundError, ValueError) as exc:
        raise AppError(404, "not_found", "File not found or link expired") from exc
    media = "application/pdf" if key.endswith(".pdf") else "image/png" if key.endswith(".png") else "image/jpeg"
    return Response(data, media_type=media, headers={"Cache-Control": "private, max-age=60"})
