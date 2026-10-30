import asyncio
import hashlib
import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nodes.decision import RULE_NAMES
from app.core import audit
from app.core.errors import AppError, not_found
from app.core.security import ANY_ROLE, CurrentUser, require_role
from app.db.models import (
    AnomalyScore,
    AuditLog,
    Claim,
    ClaimDocument,
    CoverageFinding,
    Investigation,
    Item,
    LineItem,
    Member,
    MemberPolicy,
    Procedure,
    Provider,
    Recommendation,
    Review,
    RuleFinding,
    User,
)
from app.db.session import get_session
from app.jobs.runner import enqueue
from app.services.claims import get_claim_or_404
from app.services.documents.parse import page_count, perceptual_hash, text_fingerprint
from app.services.documents.validate import UploadRejected, sniff
from app.services.jsonsafe import to_jsonable
from app.storage import spaces

from .schemas import (
    AnomalyOut,
    ClaimDetail,
    ClaimListItem,
    CoverageFindingOut,
    DocumentOut,
    LineItemOut,
    Page,
    RecommendationOut,
    ReviewOut,
    RuleFindingOut,
)

router = APIRouter(prefix="/claims", tags=["claims"])
Session = Annotated[AsyncSession, Depends(get_session)]


def mask_name(name: str) -> str:
    return " ".join(p[0] + "*" * max(2, len(p) - 1) for p in name.split() if p)


SORTS = {
    "risk": AnomalyScore.risk,
    "leakage": Recommendation.leakage_amount,
    "claimed": Claim.claimed_amount,
    "admission": Claim.admission_at,
    "id": Claim.id,
}


@router.get("", response_model=Page[ClaimListItem], dependencies=[Depends(ANY_ROLE)])
async def list_claims(
    session: Session,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
    status: str | None = None,
    tier: str | None = None,
    provider_id: str | None = None,
    action: str | None = None,
    split: str | None = None,
    q: str | None = None,
    sort: Literal["risk", "leakage", "claimed", "admission", "id"] = "risk",
    order: Literal["asc", "desc"] = "desc",
) -> Page[ClaimListItem]:
    base = (
        select(
            Claim,
            Member.id,
            Member.name,
            Provider.name,
            Procedure.name,
            Recommendation,
            AnomalyScore.risk,
            AnomalyScore.tier,
        )
        .join(MemberPolicy, MemberPolicy.id == Claim.member_policy_id)
        .join(Member, Member.id == MemberPolicy.member_id)
        .join(Provider, Provider.id == Claim.provider_id)
        .join(Procedure, Procedure.code == Claim.procedure_code)
        .outerjoin(Recommendation, Recommendation.claim_id == Claim.id)
        .outerjoin(AnomalyScore, AnomalyScore.claim_id == Claim.id)
    )
    filters = []
    if status:
        filters.append(Claim.status.in_(status.split(",")))
    if tier:
        filters.append(AnomalyScore.tier.in_(tier.split(",")))
    if provider_id:
        filters.append(Claim.provider_id == provider_id)
    if action:
        filters.append(Recommendation.action.in_(action.split(",")))
    if split:
        filters.append(Claim.split.in_(split.split(",")))
    if q:
        filters.append(Claim.id.ilike(f"%{q.strip()}%"))
    base = base.where(*filters)
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    col = SORTS[sort]
    ordering = col.desc().nulls_last() if order == "desc" else col.asc().nulls_last()
    rows = (
        await session.execute(base.order_by(ordering, Claim.id).offset((page - 1) * page_size).limit(page_size))
    ).all()
    items = [
        ClaimListItem(
            id=c.id,
            member_id=member_id,
            member_masked=mask_name(member_name),
            provider_id=c.provider_id,
            provider_name=provider_name,
            procedure_code=c.procedure_code,
            procedure_name=procedure_name,
            admission_at=c.admission_at,
            claimed_amount=c.claimed_amount,
            payable_amount=rec.payable_amount if rec else None,
            leakage_amount=rec.leakage_amount if rec else None,
            risk=float(risk) if risk is not None else None,
            tier=tier_,
            action=rec.action if rec else None,
            status=c.status,
            split=c.split,
        )
        for c, member_id, member_name, provider_name, procedure_name, rec, risk, tier_ in rows
    ]
    return Page(items=items, total=total)


class ClaimCreate(BaseModel):
    member_policy_id: str
    provider_id: str
    procedure_code: str
    diagnosis_code: str
    admission_at: date
    discharge_at: date
    claim_type: Literal["cashless", "reimbursement"] = "reimbursement"
    room_category: str = "semi_private"
    preauth_amount: Decimal | None = None

    @model_validator(mode="after")
    def _dates(self) -> "ClaimCreate":
        if self.discharge_at < self.admission_at:
            raise ValueError("discharge_at must be on or after admission_at")
        return self


@router.post("", response_model=dict, status_code=201)
async def create_claim(
    body: ClaimCreate, session: Session, user: Annotated[User, Depends(require_role("adjuster", "admin"))]
) -> dict:
    for model, key, label in (
        (MemberPolicy, body.member_policy_id, "Member policy"),
        (Provider, body.provider_id, "Provider"),
        (Procedure, body.procedure_code, "Procedure"),
    ):
        if await session.get(model, key) is None:
            raise not_found(label)
    n = (await session.execute(select(func.count()).select_from(Claim).where(Claim.split == "live"))).scalar_one()
    claim_id = f"L{n + 1:07d}"
    while await session.get(Claim, claim_id) is not None:
        n += 1
        claim_id = f"L{n + 1:07d}"
    claim = Claim(
        id=claim_id,
        member_policy_id=body.member_policy_id,
        provider_id=body.provider_id,
        procedure_code=body.procedure_code,
        diagnosis_code=body.diagnosis_code,
        admission_at=body.admission_at,
        discharge_at=body.discharge_at,
        los=max(1, (body.discharge_at - body.admission_at).days),
        room_category=body.room_category,
        room_rent_per_day=Decimal("0"),
        preauth_amount=body.preauth_amount,
        claimed_amount=Decimal("0"),
        pharmacy_amount=Decimal("0"),
        claim_type=body.claim_type,
        status="received",
        split="live",
    )
    session.add(claim)
    await session.flush()
    await audit.log(session, user, "claim_created", "claim", claim_id, body.model_dump(mode="json"))
    await session.commit()
    return {"id": claim_id, "status": claim.status}


@router.get("/{claim_id}", response_model=ClaimDetail)
async def get_claim(claim_id: str, session: Session, user: CurrentUser) -> ClaimDetail:
    from app.services.processing import pending_interrupt

    c = await get_claim_or_404(session, claim_id)
    mp = await session.get(MemberPolicy, c.member_policy_id)
    member = await session.get(Member, mp.member_id)
    provider = await session.get(Provider, c.provider_id)
    procedure = await session.get(Procedure, c.procedure_code)
    lines = (
        (await session.execute(select(LineItem).where(LineItem.claim_id == claim_id).order_by(LineItem.id)))
        .scalars()
        .all()
    )
    item_ref = {
        i.item_code: i
        for i in (
            await session.execute(
                select(Item).where(Item.item_code.in_({li.item_code for li in lines if li.item_code}))
            )
        ).scalars()
    }
    rec = await session.get(Recommendation, claim_id)
    allowed: dict[str, str] = {}
    findings = (
        (await session.execute(select(RuleFinding).where(RuleFinding.claim_id == claim_id).order_by(RuleFinding.id)))
        .scalars()
        .all()
    )
    coverage = (
        (
            await session.execute(
                select(CoverageFinding).where(CoverageFinding.claim_id == claim_id).order_by(CoverageFinding.id)
            )
        )
        .scalars()
        .all()
    )
    docs = (
        (
            await session.execute(
                select(ClaimDocument).where(ClaimDocument.claim_id == claim_id).order_by(ClaimDocument.id)
            )
        )
        .scalars()
        .all()
    )
    score = await session.get(AnomalyScore, claim_id)
    inv = await session.get(Investigation, claim_id)
    reviews = (
        await session.execute(
            select(Review, User.name)
            .join(User, User.id == Review.reviewer_id)
            .where(Review.claim_id == claim_id)
            .order_by(Review.created_at)
        )
    ).all()
    if rec:
        from app.services.rules.engine import run_rules
        from app.services.rules.loader import load_context

        ctx = await load_context(session, claim_id)
        if ctx:
            excluded = {
                f.line_item_id
                for f in coverage
                if f.verdict == "not_payable" and f.verified and f.confidence >= 0.7 and f.line_item_id
            }
            ctx.excluded_line_ids = frozenset(excluded)
            allowed = {str(k): v for k, v in run_rules(ctx).payable.allowed_by_line.items()}
    member_share = Decimal("0")
    if rec:
        member_share = rec.claimed_amount - rec.payable_amount - rec.leakage_amount
    awaiting = c.status == "pending_review"
    try:
        awaiting = awaiting and await pending_interrupt(claim_id)
    except RuntimeError:
        pass
    return ClaimDetail(
        id=c.id,
        status=c.status,
        split=c.split,
        claim_type=c.claim_type,
        bill_no=c.bill_no,
        procedure_code=c.procedure_code,
        procedure_name=procedure.name if procedure else c.procedure_code,
        diagnosis_code=c.diagnosis_code,
        admission_at=c.admission_at,
        discharge_at=c.discharge_at,
        los=c.los,
        room_category=c.room_category,
        room_rent_per_day=c.room_rent_per_day,
        preauth_amount=c.preauth_amount,
        claimed_amount=c.claimed_amount,
        pharmacy_amount=c.pharmacy_amount,
        created_at=c.created_at,
        member=to_jsonable(
            {
                "id": member.id,
                "name": member.name,
                "age": member.age,
                "gender": member.gender,
                "city": member.city,
                "member_since": member.member_since,
                "declared_conditions": member.declared_conditions,
            }
        ),
        policy=to_jsonable(
            {
                "id": mp.id,
                "product_id": mp.product_id,
                "sum_insured": mp.sum_insured,
                "balance": mp.balance,
                "start_date": mp.start_date,
                "end_date": mp.end_date,
            }
        ),
        provider=to_jsonable(
            {
                "id": provider.id,
                "name": provider.name,
                "city": provider.city,
                "city_tier": provider.city_tier,
                "hospital_tier": provider.hospital_tier,
                "nabh": provider.nabh,
                "network": provider.network,
            }
        ),
        line_items=[
            LineItemOut(
                id=li.id,
                category=li.category,
                item_code=li.item_code,
                description=li.description,
                qty=li.qty,
                unit_price=li.unit_price,
                amount=li.amount,
                service_date=li.service_date,
                document_id=li.document_id,
                page=li.page,
                bbox=li.bbox,
                mrp=item_ref[li.item_code].mrp if li.item_code in item_ref else None,
                non_payable=bool(li.item_code in item_ref and item_ref[li.item_code].non_payable),
                allowed_amount=allowed.get(str(li.id)),
            )
            for li in lines
        ],
        documents=[
            DocumentOut(
                id=d.id,
                doc_type=d.doc_type,
                filename=d.filename,
                content_type=d.content_type,
                pages=d.pages,
                parse_status=d.parse_status,
                sha256=d.sha256,
                issues=(d.extracted or {}).get("issues", []),
                route=(d.extracted or {}).get("route"),
                created_at=d.created_at,
            )
            for d in docs
        ],
        rule_findings=[
            RuleFindingOut(
                id=f.id,
                rule_code=f.rule_code,
                rule_name=RULE_NAMES.get(f.rule_code, f.rule_code),
                severity=f.severity,
                amount_impact=f.amount_impact,
                line_item_id=f.line_item_id,
                clause_ref=f.clause_ref,
                evidence=f.evidence or {},
            )
            for f in findings
        ],
        coverage_findings=[
            CoverageFindingOut(
                id=f.id,
                line_item_id=f.line_item_id,
                verdict=f.verdict,
                clause_no=f.clause_no,
                quote=f.quote,
                reason=f.reason,
                confidence=float(f.confidence),
                verified=f.verified,
                overridden=f.overridden,
            )
            for f in coverage
        ],
        anomaly=AnomalyOut(
            model_version=score.model_version,
            risk=float(score.risk),
            tier=score.tier,
            p_z=float(score.p_z),
            p_if=float(score.p_if),
            max_rz=float(score.max_rz),
            feature_z=score.feature_z,
            shap=score.shap,
            reasons=score.reasons,
        )
        if score
        else None,
        recommendation=RecommendationOut(
            action=rec.action,
            claimed_amount=rec.claimed_amount,
            payable_amount=rec.payable_amount,
            leakage_amount=rec.leakage_amount,
            member_share=member_share,
            confidence=float(rec.confidence),
            explanation=rec.explanation,
            key_findings=rec.key_findings or [],
            payable_steps=rec.payable_steps or [],
            explanation_source=rec.explanation_source,
            created_at=rec.created_at,
        )
        if rec
        else None,
        investigation=inv.report if inv else None,
        reviews=[
            ReviewOut(
                id=r.id,
                reviewer_id=r.reviewer_id,
                reviewer_name=name,
                decision=r.decision,
                final_amount=r.final_amount,
                notes=r.notes,
                created_at=r.created_at,
            )
            for r, name in reviews
        ],
        awaiting_review=awaiting,
        can_review=awaiting and user.role == "adjuster",
    )


@router.post("/{claim_id}/documents", status_code=201)
async def upload_document(
    claim_id: str,
    session: Session,
    file: Annotated[UploadFile, File()],
    user: Annotated[User, Depends(require_role("adjuster", "admin"))],
) -> dict:
    await get_claim_or_404(session, claim_id)
    data = await file.read()
    try:
        content_type, ext = sniff(data)
    except UploadRejected as exc:
        raise AppError(415, "unsupported_media_type", str(exc)) from exc
    key = f"claims/{claim_id}/{uuid.uuid4()}.{ext}"
    await asyncio.to_thread(spaces.upload, key, data, content_type)
    try:
        phash = await asyncio.to_thread(perceptual_hash, data, content_type)
        pages = await asyncio.to_thread(page_count, data, content_type)
        fingerprint = await asyncio.to_thread(text_fingerprint, data, content_type)
    except Exception as exc:  # noqa: BLE001 - corrupt file that sniffed as PDF
        await asyncio.to_thread(spaces.delete, key)
        raise AppError(415, "unsupported_media_type", "file could not be read as a document") from exc
    doc = ClaimDocument(
        claim_id=claim_id,
        doc_type="other",
        storage_key=key,
        filename=(file.filename or "")[:255],
        content_type=content_type,
        sha256=hashlib.sha256(data).hexdigest(),
        phash=phash,
        pages=pages,
        parse_status="pending",
        extracted={"text_fingerprint": fingerprint} if fingerprint else None,
    )
    session.add(doc)
    await session.flush()
    job = await enqueue(session, "parse_document", {"document_id": doc.id})
    await audit.log(
        session,
        user,
        "document_uploaded",
        "claim",
        claim_id,
        {"document_id": doc.id, "filename": doc.filename, "content_type": content_type, "bytes": len(data)},
    )
    await session.commit()
    return {"id": doc.id, "job_id": job.id, "content_type": content_type, "pages": pages}


@router.get("/{claim_id}/documents/{doc_id}/url", dependencies=[Depends(ANY_ROLE)])
async def document_url(claim_id: str, doc_id: int, session: Session) -> dict:
    doc = await session.get(ClaimDocument, doc_id)
    if doc is None or doc.claim_id != claim_id:
        raise not_found("Document")
    return {"url": spaces.presign(doc.storage_key, expires=300), "expires_in": 300, "content_type": doc.content_type}


@router.post("/{claim_id}/process", status_code=202)
async def process(
    claim_id: str, session: Session, user: Annotated[User, Depends(require_role("adjuster", "manager", "admin"))]
) -> dict:
    claim = await get_claim_or_404(session, claim_id)
    if claim.status == "processing":
        raise AppError(409, "conflict", "Claim is already processing")
    job = await enqueue(session, "process_claim", {"claim_id": claim_id})
    await audit.log(session, user, "process_requested", "claim", claim_id, {"job_id": job.id})
    await session.commit()
    return {"job_id": job.id}


class ReviewIn(BaseModel):
    decision: Literal["approve", "approve_with_deductions", "query", "investigate", "refer_siu", "reject"]
    final_amount: Decimal = Field(ge=0)
    notes: str | None = Field(default=None, max_length=4000)


@router.post("/{claim_id}/review")
async def review(
    claim_id: str, body: ReviewIn, session: Session, user: Annotated[User, Depends(require_role("adjuster"))]
) -> dict:
    from app.services.processing import pending_interrupt, resume_review

    claim = await get_claim_or_404(session, claim_id)
    rec = await session.get(Recommendation, claim_id)
    if claim.status != "pending_review" or rec is None or not await pending_interrupt(claim_id):
        raise AppError(409, "conflict", "Claim is not awaiting review")
    overriding = body.decision != rec.action or body.final_amount != rec.payable_amount
    if overriding and not (body.notes and body.notes.strip()):
        raise AppError(422, "validation_error", "Notes are required when overriding the recommendation")
    if body.decision in ("reject",) and body.final_amount != 0:
        raise AppError(422, "validation_error", "A rejected claim must have a final amount of 0")
    if body.final_amount > claim.claimed_amount:
        raise AppError(422, "validation_error", "Final amount cannot exceed the claimed amount")
    await session.commit()
    payload = {
        "decision": body.decision,
        "final_amount": str(body.final_amount),
        "notes": body.notes,
        "reviewer_id": user.id,
        "overrides": {
            "action": [rec.action, body.decision],
            "amount": [str(rec.payable_amount), str(body.final_amount)],
        }
        if overriding
        else None,
    }
    result = await resume_review(claim_id, payload)
    return {"ok": True, "claim_id": claim_id, "errors": result["errors"]}


class CoverageOverrideIn(BaseModel):
    verdict: Literal["payable", "not_payable", "partially_payable", "needs_review"]
    note: str = Field(min_length=3, max_length=2000)


@router.post("/{claim_id}/coverage/{finding_id}/override")
async def override_coverage(
    claim_id: str,
    finding_id: int,
    body: CoverageOverrideIn,
    session: Session,
    user: Annotated[User, Depends(require_role("adjuster"))],
) -> dict:
    """Records the adjuster's interpretation as a clause note (memory) used by future coverage runs."""
    from app.agents import runtime

    f = await session.get(CoverageFinding, finding_id)
    if f is None or f.claim_id != claim_id:
        raise not_found("Coverage finding")
    claim = await session.get(Claim, claim_id)
    mp = await session.get(MemberPolicy, claim.member_policy_id)
    li = await session.get(LineItem, f.line_item_id) if f.line_item_id else None
    f.overridden = {"from": f.verdict, "to": body.verdict, "note": body.note, "by": user.id}
    if f.clause_no:
        await runtime.store().aput(
            ("clauses", mp.product_id, f.clause_no),
            f"{claim_id}:{finding_id}",
            {
                "text": body.note,
                "clause_no": f.clause_no,
                "item": li.description if li else None,
                "from_verdict": f.verdict,
                "to_verdict": body.verdict,
                "claim_id": claim_id,
                "by": user.name,
            },
        )
    await audit.log(
        session,
        user,
        "coverage_override",
        "claim",
        claim_id,
        {"finding_id": finding_id, "from": f.verdict, "to": body.verdict, "note": body.note, "clause_no": f.clause_no},
    )
    await session.commit()
    return {"ok": True}


@router.get("/{claim_id}/peer-distribution", dependencies=[Depends(ANY_ROLE)])
async def peer_distribution(claim_id: str, feature: str) -> dict:
    from app.agents.tools.readonly import peer_distribution as dist

    result = await dist(claim_id, feature, sample=500)
    if "error" in result:
        raise AppError(404 if "not found" in result["error"] else 400, "bad_request", result["error"])
    return result


@router.get("/{claim_id}/audit", dependencies=[Depends(ANY_ROLE)])
async def claim_audit(claim_id: str, session: Session) -> dict:
    rows = (
        (
            await session.execute(
                select(AuditLog)
                .where(AuditLog.entity == "claim", AuditLog.entity_id == claim_id)
                .order_by(AuditLog.created_at, AuditLog.id)
            )
        )
        .scalars()
        .all()
    )
    users = {u.id: u.name for u in (await session.execute(select(User))).scalars()}
    return {
        "items": [
            {
                **r.as_dict(),
                "actor_name": users.get(int(r.actor_id))
                if r.actor_type == "user" and r.actor_id.isdigit()
                else r.actor_id,
            }
            for r in rows
        ],
        "total": len(rows),
    }
