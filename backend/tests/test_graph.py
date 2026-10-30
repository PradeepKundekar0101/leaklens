"""Integration: run the orchestrator on fixed claims against the test database (no LLM keys).

Covers: approve_with_deductions with the correct payable, a duplicate -> refer_siu, a clean approval,
human-review interrupt, and resume after a runtime restart.
"""

from datetime import date, timedelta
from decimal import Decimal as D

import numpy as np
import pytest
from sqlalchemy import text

from tests.conftest import login

pytestmark = pytest.mark.db

ADM = date(2026, 9, 10)


async def _seed() -> None:
    from app.db.models import (
        Agent,
        Claim,
        Item,
        LineItem,
        Member,
        MemberPolicy,
        PolicyParams,
        PolicyProduct,
        Procedure,
        Provider,
    )
    from app.db.session import session_scope

    async with session_scope() as s:
        await s.execute(
            text(
                "TRUNCATE claims, line_items, rule_findings, coverage_findings, anomaly_scores, recommendations, "
                "investigations, reviews, member_policies, members, agents, providers, tariffs, procedures, items, "
                "policy_params, policy_products, peer_stats, model_registry, jobs RESTART IDENTITY CASCADE"
            )
        )
        s.add(
            Procedure(
                code="PR_APPX",
                name="Appendectomy",
                category="surgery",
                icd10="K35",
                base_rate=D("60000"),
                typical_los=3,
                typical_pharmacy_share=0.15,
                age_profile={"mean": 35},
                frequency=1,
                waiting_category="none",
            )
        )
        s.add_all(
            [
                Item(
                    item_code="DRUG1",
                    name="Ceftriaxone 1g",
                    category="pharmacy",
                    mrp=D("100"),
                    non_payable=False,
                    source="t",
                ),
                Item(
                    item_code="GLOVES",
                    name="Surgical gloves",
                    category="consumables",
                    mrp=D("50"),
                    non_payable=True,
                    source="t",
                ),
            ]
        )
        s.add(
            Provider(
                id="H001",
                name="Test Hospital",
                city="Pune",
                city_tier=1,
                hospital_tier=1,
                nabh=True,
                beds=200,
                network=True,
                joined_at=date(2020, 1, 1),
            )
        )
        s.add(Agent(id="A001", name="Agent", channel="direct"))
        s.add(PolicyProduct(id="GOLD", name="Gold", version="1"))
        await s.flush()
        s.add(
            PolicyParams(
                product_id="GOLD",
                room_rent_cap_pct=1.0,
                icu_cap_pct=2.0,
                copay_pct=0,
                deductible=D("0"),
                sub_limits={},
                waiting_periods={
                    "initial_days": 30,
                    "listed_conditions_months": 24,
                    "pre_existing_months": 36,
                    "listed_procedures": [],
                },
                clause_refs={"room_rent_cap_pct": "4.2"},
            )
        )
        rng = np.random.default_rng(1)
        for i in range(80):
            mid, pid = f"M{i:06d}", f"MP{i:06d}"
            s.add(
                Member(
                    id=mid,
                    name=f"Member {i}",
                    age=int(rng.integers(20, 70)),
                    gender="F",
                    city="Pune",
                    member_since=date(2021, 1, 1),
                    declared_conditions=[],
                    bank_account_hash="x",
                    phone_hash="y",
                )
            )
            await s.flush()
            s.add(
                MemberPolicy(
                    id=pid,
                    member_id=mid,
                    product_id="GOLD",
                    sum_insured=D("500000"),
                    balance=D("500000"),
                    start_date=date(2023, 1, 1),
                    end_date=date(2027, 1, 1),
                    agent_id="A001",
                )
            )
        await s.flush()

        def claim(cid: str, mp: str, split: str, amount: D, rent: D, adm: date, los: int = 3) -> list:
            pharmacy = (amount * D("0.15")).quantize(D("0.01"))
            room = rent * los
            rest = amount - pharmacy - room
            c = Claim(
                id=cid,
                member_policy_id=mp,
                provider_id="H001",
                procedure_code="PR_APPX",
                diagnosis_code="K35",
                admission_at=adm,
                discharge_at=adm + timedelta(days=los),
                los=los,
                room_category="private",
                room_rent_per_day=rent,
                preauth_amount=amount,
                claimed_amount=amount,
                pharmacy_amount=pharmacy,
                claim_type="cashless",
                status="received",
                split=split,
            )
            lines = [
                LineItem(
                    claim_id=cid,
                    category="room",
                    item_code="ROOM",
                    description="Room rent",
                    qty=los,
                    unit_price=rent,
                    amount=room,
                    service_date=adm,
                ),
                LineItem(
                    claim_id=cid,
                    category="surgeon",
                    item_code="SURGEON",
                    description="Surgeon fee",
                    qty=1,
                    unit_price=rest,
                    amount=rest,
                    service_date=adm,
                ),
                LineItem(
                    claim_id=cid,
                    category="pharmacy",
                    item_code="PHARMA_MISC",
                    description="Medicines",
                    qty=1,
                    unit_price=pharmacy,
                    amount=pharmacy,
                    service_date=adm,
                ),
            ]
            return [c, *lines]

        for i in range(70):
            amt = D(str(round(float(rng.normal(60000, 4000)), 2)))
            for obj in claim(f"T{i:05d}", f"MP{i:06d}", "train", amt, D("4000"), date(2026, 3, 1)):
                s.add(obj)
                await s.flush()
        # test claims
        for obj in claim("CLEAN1", "MP000070", "test", D("60000.00"), D("4000"), ADM):
            s.add(obj)
        for obj in claim("ROOM1", "MP000071", "test", D("60000.00"), D("7000"), ADM):
            s.add(obj)
        for obj in claim("DUPA", "MP000072", "test", D("61000.00"), D("4000"), ADM):
            s.add(obj)
        await s.flush()
        for obj in claim("DUPB", "MP000072", "test", D("61000.00"), D("4000"), ADM):
            s.add(obj)
        await s.commit()
    from app.services.anomaly import scorer
    from app.services.anomaly.iforest import train_and_register

    async with session_scope() as s:
        await train_and_register(s, activate=True)
        await s.commit()
    await scorer.load_active()


async def test_process_room_rent_claim_gives_deductions(seeded):
    from app.services.processing import pending_interrupt, process_claim

    out = await process_claim("ROOM1")
    # rent 7,000 vs cap 5,000 for 3 days: excess 6,000; surgeon fee scaled by 5/7
    assert out["action"] in ("approve_with_deductions", "refer_siu")
    assert D(out["leakage"]) > D("6000")
    assert await pending_interrupt("ROOM1")


async def test_payable_matches_rules_engine(seeded):
    from app.db.models import Recommendation
    from app.db.session import session_scope
    from app.services.rules.engine import run_rules
    from app.services.rules.loader import load_context

    async with session_scope() as s:
        rec = await s.get(Recommendation, "ROOM1")
        ctx = await load_context(s, "ROOM1")
    expected = run_rules(ctx).payable
    assert rec.payable_amount == expected.payable
    assert rec.leakage_amount == expected.leakage
    assert rec.explanation_source == "template"


async def test_duplicate_is_referred(seeded):
    from app.services.processing import process_claim

    assert (await process_claim("DUPB"))["action"] == "refer_siu"


async def test_review_resumes_after_runtime_restart(seeded, client, users):
    from app.agents import runtime
    from app.db.models import Claim, Review
    from app.db.session import session_scope
    from app.services.processing import process_claim

    out = await process_claim("CLEAN1")
    assert out["action"] in ("approve", "investigate")
    # Simulate a server restart: drop the compiled graph and its pool, then start again.
    await runtime.shutdown()
    await runtime.startup()

    await login(client, users["adjuster"])
    detail = (await client.get("/api/v1/claims/CLEAN1")).json()
    assert detail["awaiting_review"] and detail["can_review"]
    payable = detail["recommendation"]["payable_amount"]
    r = await client.post(
        "/api/v1/claims/CLEAN1/review", json={"decision": detail["recommendation"]["action"], "final_amount": payable}
    )
    assert r.status_code == 200, r.text
    async with session_scope() as s:
        claim = await s.get(Claim, "CLEAN1")
        assert claim.status in ("approved", "investigating")
        reviews = (await s.execute(text("SELECT count(*) FROM reviews WHERE claim_id = 'CLEAN1'"))).scalar_one()
        assert reviews == 1
        assert Review is not None


async def test_override_requires_notes_and_auditor_cannot_review(seeded, client, users):
    await login(client, users["adjuster"])
    r = await client.post("/api/v1/claims/ROOM1/review", json={"decision": "approve", "final_amount": "60000.00"})
    assert r.status_code == 422
    await login(client, users["auditor"])
    detail = (await client.get("/api/v1/claims/ROOM1")).json()
    assert detail["can_review"] is False
    r = await client.post(
        "/api/v1/claims/ROOM1/review", json={"decision": "approve", "final_amount": "1", "notes": "x"}
    )
    assert r.status_code == 403


async def test_stored_explanations_pass_number_guardrail(seeded):
    from app.db.models import Recommendation
    from app.db.session import session_scope
    from app.services.llm.guardrail import check_numbers

    async with session_scope() as s:
        recs = (await s.execute(text("SELECT claim_id FROM recommendations"))).scalars().all()
        for cid in recs:
            rec = await s.get(Recommendation, cid)
            payload = {
                "steps": rec.payable_steps,
                "claimed": str(rec.claimed_amount),
                "payable": str(rec.payable_amount),
                "leakage": str(rec.leakage_amount),
                "findings": (
                    await s.execute(
                        text(
                            "SELECT rule_code, amount_impact::text, clause_ref FROM rule_findings WHERE claim_id = :c"
                        ),
                        {"c": cid},
                    )
                )
                .mappings()
                .all(),
            }
            assert check_numbers(rec.explanation, [dict(x) if hasattr(x, "keys") else x for x in [payload]]) == [], cid


async def test_dashboard_totals_reconcile_with_recommendations(seeded, client, users):
    from decimal import Decimal

    from app.db.session import session_scope

    await login(client, users["manager"])
    kpis = (await client.get("/api/v1/dashboard/summary")).json()["kpis"]
    async with session_scope() as s:
        total, n = (
            await s.execute(text("SELECT COALESCE(sum(leakage_amount), 0), count(*) FROM recommendations"))
        ).one()
    assert Decimal(kpis["leakage_identified"]) == total
    assert kpis["processed"] == n


async def test_every_agent_tool_returns_data(seeded):
    """Each read-only tool runs end to end against seeded data without raising or returning an error."""
    from app.agents.tools import readonly as t

    calls = [
        t.get_member_history(t.MemberIn(member_id="M000070")),
        t.get_provider_profile(t.ProviderIn(provider_id="H001")),
        t.find_near_duplicates(t.ClaimIn(claim_id="DUPB")),
        t.get_policy_params(t.ProductIn(product_id="GOLD")),
        t.get_claim_state(t.ClaimIn(claim_id="ROOM1")),
        t.get_peer_distribution(t.PeerIn(claim_id="ROOM1", feature="log_amount")),
        t.get_document_text(t.DocumentTextIn(claim_id="ROOM1")),
        t.search_similar_cases(t.SimilarCasesIn(query="appendectomy room rent")),
        t.get_clause_notes(t.ClauseNotesIn(product_id="GOLD", clause_no="4.2")),
    ]
    for result in [await c for c in calls]:
        assert "error" not in result, result
    history = await t.get_member_history(t.MemberIn(member_id="M000072"))
    assert {c["claim_id"] for c in history["claims"]} >= {"DUPA", "DUPB"}
    dupes = await t.find_near_duplicates(t.ClaimIn(claim_id="DUPB"))
    assert [d["claim_id"] for d in dupes["near_duplicates"]] == ["DUPA"]


async def test_coverage_override_note_reaches_coverage_agent_tool(seeded, client, users):
    from app.agents.tools import readonly as t
    from app.db.models import CoverageFinding, LineItem
    from app.db.session import session_scope

    async with session_scope() as s:
        line = (await s.execute(text("SELECT id FROM line_items WHERE claim_id = 'ROOM1' LIMIT 1"))).scalar_one()
        finding = CoverageFinding(
            claim_id="ROOM1",
            line_item_id=line,
            verdict="not_payable",
            clause_no="4.2",
            quote="x",
            reason="r",
            confidence=0.8,
            verified=True,
        )
        s.add(finding)
        await s.commit()
        finding_id = finding.id
        assert LineItem is not None
    await login(client, users["adjuster"])
    r = await client.post(
        f"/api/v1/claims/ROOM1/coverage/{finding_id}/override",
        json={"verdict": "payable", "note": "Private room is covered for this product tier"},
    )
    assert r.status_code == 200, r.text
    notes = await t.get_clause_notes(t.ClauseNotesIn(product_id="GOLD", clause_no="4.2"))
    assert any("Private room is covered" in n["text"] for n in notes["notes"])
