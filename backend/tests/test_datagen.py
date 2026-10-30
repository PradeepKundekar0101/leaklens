"""Phase 1 acceptance tests for the synthetic data generator, policy wordings and sample documents."""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

import imagehash
import pandas as pd
import pytest

from scripts.datagen.common import load_products, load_reference, to_paise
from scripts.datagen.documents import CANARY_TEXT, TOTAL_LABELS, page1_phash, pdf_pages, pdf_text
from scripts.generate_data import generate
from scripts.generate_policy_docs import render

SMALL = {"seed": 42, "n_train": 2000, "n_test": 400}


@pytest.fixture(scope="module")
def small_run(tmp_path_factory) -> tuple[Path, dict]:
    out = tmp_path_factory.mktemp("gen_a")
    report = generate(out=out, quiet=True, **SMALL)
    return out, report


def _read(out: Path, name: str) -> pd.DataFrame:
    return pd.read_csv(out / name, dtype=str, keep_default_na=False)


def test_generator_has_no_construction_errors(small_run):
    _, report = small_run
    assert report["construction_errors"] == []
    assert report["n_train"] > 1900 and report["n_test"] > 380


def test_line_items_sum_exactly_to_claimed(small_run):
    out, _ = small_run
    claims = _read(out, "claims.csv")
    lines = _read(out, "line_items.csv")
    lines["p"] = lines.amount.map(to_paise)
    lines["qp"] = [to_paise(u) * int(q) for u, q in zip(lines.unit_price, lines.qty, strict=True)]
    assert (lines.p == lines.qp).all(), "amount must equal qty x unit_price"
    totals = lines.groupby("claim_id").p.sum()
    claimed = claims.set_index("id").claimed_amount.map(to_paise)
    assert set(totals.index) == set(claimed.index)
    assert (totals.loc[claimed.index] == claimed).all()
    pharm = lines[lines.category == "pharmacy"].groupby("claim_id").p.sum()
    assert (claims.set_index("id").pharmacy_amount.map(to_paise).loc[pharm.index] == pharm).all()


def test_service_dates_within_stay_except_planted(small_run):
    out, _ = small_run
    claims = _read(out, "claims.csv").set_index("id")
    lines = _read(out, "line_items.csv")
    gt = _read(out, "ground_truth.csv")
    adm = lines.claim_id.map(claims.admission_at)
    dis = lines.claim_id.map(claims.discharge_at)
    outside = set(lines.claim_id[(lines.service_date < adm) | (lines.service_date > dis)])
    planted = set(gt.claim_id[gt.scenario == "service_date_outside_stay"])
    assert outside == planted
    assert planted, "expected some planted service-date cases"


def test_ground_truth_shape(small_run):
    out, _ = small_run
    gt = _read(out, "ground_truth.csv")
    claims = _read(out, "claims.csv")
    assert set(gt.claim_id) <= set(claims.id)
    assert (gt.leakage_amount.map(to_paise) > 0).all()
    expected = {
        "room_rent_above_cap",
        "non_payable_billed",
        "item_above_mrp",
        "above_tariff",
        "exact_duplicate",
        "service_date_outside_stay",
        "inflated_pharmacy",
        "stretched_stay",
        "preauth_escalation",
        "early_claim",
        "combination",
        "overbilling_provider",
        "reused_document",
    }
    assert set(gt.scenario) == expected
    assert set(gt.claim_id[gt.scenario == "reused_document"]) <= set(claims.id[claims.split == "test"])


def test_calibration_small_run_in_target(small_run):
    _, report = small_run
    assert 5.0 <= report["leakage_pct"] <= 10.0


def test_calibration_default_size_in_target(tmp_path):
    report = generate(out=tmp_path, documents=False, quiet=True)
    assert report["construction_errors"] == []
    assert 5.0 <= report["leakage_pct"] <= 10.0
    assert report["seconds_data"] < 60


def test_same_seed_is_byte_identical(small_run, tmp_path):
    out_a, _ = small_run
    generate(out=tmp_path, quiet=True, **SMALL)

    def digest(root: Path) -> dict[str, str]:
        return {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*"))
            if p.is_file()
        }

    a, b = digest(out_a), digest(tmp_path)
    assert a.keys() == b.keys()
    assert a == b


def test_policy_pdfs_contain_every_clause_ref(tmp_path):
    ref = load_reference()
    for product in load_products(ref):
        path = render(product, ref, tmp_path)
        text = pdf_text(path.read_bytes())
        assert 25 <= pdf_pages(path.read_bytes()) <= 40
        for key, clause in product.clause_refs.items():
            assert re.search(rf"(?m)^\s*{re.escape(clause)} \S", text), f"{product.id}: clause {clause} ({key})"
        # parameter values appear in the wording
        flat = re.sub(r"\s+", " ", text)
        if product.room_rent_cap_pct:
            pct = product.room_rent_cap_pct.rstrip("0").rstrip(".")
            assert f"{pct}% of the Sum Insured per day" in flat
        for value in product.sub_limits.values():
            assert f"Rs {_indian(int(Decimal(value)))}" in flat, f"{product.id}: sub-limit {value}"
        wp = product.waiting_periods
        assert f"{wp['listed_conditions_months']} months" in flat and f"{wp['initial_days']} days" in flat


def _indian(n: int) -> str:
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    return ",".join(([head] if head else []) + parts + [tail])


def test_policy_params_csv_matches_products(small_run):
    out, _ = small_run
    params = _read(out, "policy_params.csv").set_index("product_id")
    ref = load_reference()
    for product in load_products(ref):
        row = params.loc[product.id]
        assert json.loads(row.clause_refs) == product.clause_refs
        assert json.loads(row.sub_limits) == product.sub_limits
        assert (row.room_rent_cap_pct or None) == product.room_rent_cap_pct


def test_sample_bills_print_line_item_totals(small_run):
    out, _ = small_run
    man = _read(out, "documents_manifest.csv")
    lines = _read(out, "line_items.csv")
    totals = lines.assign(p=lines.amount.map(to_paise)).groupby("claim_id").p.sum()
    bills = man[(man.doc_type == "bill") & (man.scanned == "false")]
    assert len(bills) >= 30
    label = "|".join(TOTAL_LABELS)
    for r in bills.itertuples():
        text = pdf_text((out / "documents" / r.filename).read_bytes())
        m = re.search(rf"(?:{label}): Rs ([\d,]+\.\d\d)", text)
        assert m, f"no total in {r.filename}"
        source = r.reused_from or r.claim_id  # a reused bill shows the original claim's charges
        assert to_paise(m.group(1).replace(",", "")) == totals[source], r.filename
    assert (man.scanned == "true").sum() >= 3
    assert man.claim_id.nunique() >= 40


def test_canary_bill_present(small_run):
    out, _ = small_run
    man = _read(out, "documents_manifest.csv")
    canary = man[man.canary == "true"]
    assert len(canary) == 1
    assert CANARY_TEXT in pdf_text((out / "documents" / canary.filename.iloc[0]).read_bytes())


def test_reused_bill_pairs_match_by_hash(small_run):
    out, _ = small_run
    man = _read(out, "documents_manifest.csv")
    gt = _read(out, "ground_truth.csv")
    reused = man[man.reused_from != ""]
    assert len(reused) >= 1
    assert set(reused.claim_id) == set(gt.claim_id[gt.scenario == "reused_document"])
    for r in reused.itertuples():
        src = man[(man.claim_id == r.reused_from) & (man.doc_type == "bill")].filename.iloc[0]
        a = (out / "documents" / src).read_bytes()
        b = (out / "documents" / r.filename).read_bytes()
        if r.scanned == "false":
            assert hashlib.sha256(a).digest() == hashlib.sha256(b).digest()
        dist = imagehash.hex_to_hash(page1_phash(a)) - imagehash.hex_to_hash(page1_phash(b))
        assert dist <= 5, (r.filename, dist)
