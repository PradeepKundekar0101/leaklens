import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.errors import AppError, not_found
from app.core.security import ANY_ROLE, require_role
from app.db.models import PolicyChunk, PolicyParams, PolicyProduct, User
from app.db.session import get_session
from app.jobs.runner import enqueue
from app.services.documents.validate import UploadRejected, sniff
from app.services.jsonsafe import to_jsonable
from app.services.policy import params as policy_params
from app.services.policy import search as policy_search
from app.storage import spaces

router = APIRouter(prefix="/policies", tags=["policies"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("", dependencies=[Depends(ANY_ROLE)])
async def list_policies(session: Session) -> dict:
    products = (await session.execute(select(PolicyProduct).order_by(PolicyProduct.id))).scalars().all()
    counts = dict(
        (await session.execute(select(PolicyChunk.product_id, func.count()).group_by(PolicyChunk.product_id))).all()
    )
    items = []
    for p in products:
        params = await session.get(PolicyParams, p.id)
        current = policy_params.current_as_comparable(params) if params else None
        proposed = params.proposed if params else None
        items.append(
            to_jsonable(
                {
                    "id": p.id,
                    "name": p.name,
                    "version": p.version,
                    "status": p.status,
                    "has_wording": bool(p.wording_key),
                    "chunks": counts.get(p.id, 0),
                    "params": current,
                    "approved_by": params.approved_by if params else None,
                    "approved_at": params.approved_at if params else None,
                    "proposed": proposed,
                    "diff": policy_params.diff(current, proposed) if current and proposed else [],
                }
            )
        )
    return {"items": items, "total": len(items)}


@router.get("/{product_id}/chunks", dependencies=[Depends(ANY_ROLE)])
async def chunks(
    product_id: str,
    session: Session,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    clause_type: str | None = None,
) -> dict:
    q = select(PolicyChunk).where(PolicyChunk.product_id == product_id)
    if clause_type:
        q = q.where(PolicyChunk.clause_type == clause_type)
    total = (await session.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = (await session.execute(q.order_by(PolicyChunk.id).offset((page - 1) * page_size).limit(page_size))).scalars()
    return {
        "items": [
            {
                "id": c.id,
                "clause_no": c.clause_no,
                "section_path": c.section_path,
                "clause_type": c.clause_type,
                "page": c.page,
                "text": c.text,
            }
            for c in rows
        ],
        "total": total,
    }


@router.get("/{product_id}/clauses/{clause_no}", dependencies=[Depends(ANY_ROLE)])
async def clause(product_id: str, clause_no: str, session: Session) -> dict:
    rows = (
        (
            await session.execute(
                select(PolicyChunk)
                .where(PolicyChunk.product_id == product_id, PolicyChunk.clause_no == clause_no)
                .order_by(PolicyChunk.id)
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        raise not_found("Clause")
    return {
        "clause_no": clause_no,
        "section_path": rows[0].section_path,
        "page": rows[0].page,
        "text": "\n\n".join(r.text for r in rows),
    }


@router.get("/{product_id}/search", dependencies=[Depends(ANY_ROLE)])
async def search(product_id: str, q: str, session: Session, clause_type: str | None = None) -> dict:
    results = await policy_search.search(session, product_id, q, clause_type)
    return {"items": results, "total": len(results)}


@router.post("/{product_id}/ingest", status_code=202)
async def ingest(
    product_id: str,
    session: Session,
    user: Annotated[User, Depends(require_role("admin"))],
    file: Annotated[UploadFile | None, File()] = None,
) -> dict:
    product = await session.get(PolicyProduct, product_id)
    if product is None:
        raise not_found("Policy product")
    if file is not None:
        data = await file.read()
        try:
            content_type, _ = sniff(data)
        except UploadRejected as exc:
            raise AppError(415, "unsupported_media_type", str(exc)) from exc
        if content_type != "application/pdf":
            raise AppError(415, "unsupported_media_type", "policy wording must be a PDF")
        key = f"policies/{product_id}.pdf"
        await asyncio.to_thread(spaces.upload, key, data, content_type)
        product.wording_key = key
    if not product.wording_key:
        raise AppError(400, "bad_request", "upload a wording PDF first")
    job = await enqueue(session, "ingest_policy", {"product_id": product_id, "user_id": user.id})
    await audit.log(session, user, "policy_ingest_requested", "policy", product_id, {"job_id": job.id})
    await session.commit()
    return {"job_id": job.id}


@router.post("/{product_id}/params/extract", status_code=200)
async def extract_params(
    product_id: str, session: Session, user: Annotated[User, Depends(require_role("admin"))]
) -> dict:
    try:
        result = await policy_params.extract(session, product_id)
    except ValueError as exc:
        raise AppError(400, "bad_request", str(exc)) from exc
    await audit.log(session, user, "params_extracted", "policy", product_id, {"ok": result.get("ok")})
    await session.commit()
    return result


@router.post("/{product_id}/params/approve")
async def approve_params(
    product_id: str, session: Session, user: Annotated[User, Depends(require_role("admin"))]
) -> dict:
    params = await session.get(PolicyParams, product_id)
    before = policy_params.current_as_comparable(params) if params else None
    try:
        updated = await policy_params.approve(session, product_id, user.email)
    except ValueError as exc:
        raise AppError(400, "bad_request", str(exc)) from exc
    after = policy_params.current_as_comparable(updated)
    await audit.log(session, user, "params_approved", "policy", product_id, {"before": before, "after": after})
    await session.commit()
    return {"ok": True, "params": after}
