"""Load reference CSVs, the generated portfolio and the sample documents into Postgres (idempotent).

    cd backend && uv run python -m scripts.load_data [--data ../data/generated] [--skip-documents]

Truncates and reloads (TRUNCATE ... RESTART IDENTITY CASCADE) the reference, master, claims and analysis tables for
the database in DATABASE_URL (APP_ENV is printed for confirmation), bulk-loads with COPY, uploads the sample
documents through app.storage.spaces at claims/{claim_id}/{uuid}.pdf with sha256 + perceptual hash, and uploads the
policy wordings at policies/{product_id}.pdf. users, jobs, audit_log, peer_stats, model_registry and policy_chunks
are left untouched.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import sys
import time
import uuid
from pathlib import Path

import psycopg

from scripts.datagen.common import DEFAULT_OUT, POLICIES_DIR, REFERENCE_DIR
from scripts.datagen.documents import page1_phash, pdf_pages

# (table, source file, columns in table order). Source files may carry extra columns, which are dropped.
REFERENCE = [
    (
        "procedures",
        "procedures.csv",
        [
            "code",
            "name",
            "category",
            "icd10",
            "base_rate",
            "typical_los",
            "typical_pharmacy_share",
            "age_profile",
            "frequency",
            "waiting_category",
        ],
    ),
    ("items", "items.csv", ["item_code", "name", "category", "mrp", "non_payable", "source"]),
    ("multipliers", "multipliers.csv", ["factor_type", "key", "value"]),
]
GENERATED = [
    ("providers", ["id", "name", "city", "city_tier", "hospital_tier", "nabh", "beds", "network", "joined_at"]),
    ("tariffs", ["provider_id", "procedure_code", "package_rate"]),
    ("agents", ["id", "name", "channel"]),
    (
        "members",
        [
            "id",
            "name",
            "age",
            "gender",
            "city",
            "member_since",
            "declared_conditions",
            "bank_account_hash",
            "phone_hash",
        ],
    ),
    ("policy_products", ["id", "name", "version", "wording_key", "status"]),
    (
        "policy_params",
        [
            "product_id",
            "room_rent_cap_pct",
            "icu_cap_pct",
            "copay_pct",
            "deductible",
            "sub_limits",
            "waiting_periods",
            "clause_refs",
            "approved_by",
            "approved_at",
        ],
    ),
    (
        "member_policies",
        ["id", "member_id", "product_id", "sum_insured", "balance", "start_date", "end_date", "agent_id"],
    ),
    (
        "claims",
        [
            "id",
            "member_policy_id",
            "provider_id",
            "procedure_code",
            "diagnosis_code",
            "admission_at",
            "discharge_at",
            "los",
            "room_category",
            "room_rent_per_day",
            "preauth_amount",
            "claimed_amount",
            "pharmacy_amount",
            "claim_type",
            "status",
            "split",
            "bill_no",
            "created_at",
        ],
    ),
    ("line_items", ["claim_id", "category", "item_code", "description", "qty", "unit_price", "amount", "service_date"]),
    ("ground_truth", ["claim_id", "scenario", "leakage_amount"]),
]
# Analysis tables reference claims; they are cleared so no finding outlives the claim it was computed for.
ANALYSIS = [
    "rule_findings",
    "coverage_findings",
    "anomaly_scores",
    "recommendations",
    "investigations",
    "reviews",
    "provider_stats",
    "claim_documents",
]
DOC_NAMESPACE = uuid.UUID("6f1c2a9e-4b7d-4c1e-9a52-0d3b8e7f5a10")


def database_url() -> tuple[str, str]:
    from app.core.config import get_settings

    s = get_settings()
    return s.database_url.replace("postgresql+psycopg://", "postgresql://"), s.app_env


def blockers(url: str) -> str:
    with psycopg.connect(url, autocommit=True) as c:
        rows = c.execute(
            "SELECT pid, state, left(query, 60) FROM pg_stat_activity WHERE datname = current_database() "
            "AND pid <> pg_backend_pid() AND state LIKE 'idle in transaction%'"
        ).fetchall()
    return "; ".join(f"pid {p} {st}: {q!r}" for p, st, q in rows) or "unknown"


def copy_csv(cur: psycopg.Cursor, table: str, path: Path, columns: list[str]) -> int:
    with path.open(newline="") as f:
        header = next(csv.reader(f))
    missing = [c for c in columns if c not in header]
    if missing:
        raise ValueError(f"{path}: missing columns {missing}")
    cols = ", ".join(columns)
    sql = f"COPY {table} ({cols}) FROM STDIN WITH (FORMAT csv, HEADER true)"
    if header == columns:
        with path.open("rb") as f, cur.copy(sql) as cp:
            while chunk := f.read(1 << 20):
                cp.write(chunk)
    else:
        idx = [header.index(c) for c in columns]
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        with path.open(newline="") as f:
            for row in csv.reader(f):
                w.writerow([row[i] for i in idx])
        with cur.copy(sql) as cp:
            cp.write(buf.getvalue().encode())
    cur.execute(f"SELECT count(*) FROM {table}")
    return cur.fetchone()[0]


def load(data_dir: Path, skip_documents: bool = False) -> dict[str, int]:
    from app.storage import spaces

    url, env = database_url()
    host = url.split("@")[-1]
    print(f"APP_ENV={env} database={host}")
    t0 = time.perf_counter()
    counts: dict[str, int] = {}
    tables = [t for t, _, _ in REFERENCE] + [t for t, _ in GENERATED] + ANALYSIS
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        # TRUNCATE needs exclusive locks; fail fast (instead of deadlocking) if the API / worker holds them.
        cur.execute("SET lock_timeout = '15s'")
        cur.execute("SELECT storage_key FROM claim_documents")
        old_keys = {r[0] for r in cur.fetchall()}
        try:
            cur.execute(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE")
        except (psycopg.errors.LockNotAvailable, psycopg.errors.DeadlockDetected) as exc:
            raise SystemExit(
                f"tables are locked by other sessions ({blockers(url)}); stop the API / worker and "
                f"retry: {exc.diag.message_primary}"
            ) from exc
        for table, fname, cols in REFERENCE:
            counts[table] = copy_csv(cur, table, REFERENCE_DIR / fname, cols)
        for table, cols in GENERATED:
            counts[table] = copy_csv(cur, table, data_dir / f"{table}.csv", cols)
        cur.execute("UPDATE policy_params SET approved_at = now()")

        # policy wordings
        cur.execute("SELECT id FROM policy_products ORDER BY id")
        for (pid,) in cur.fetchall():
            pdf = POLICIES_DIR / f"{pid}.pdf"
            if not pdf.exists():
                print(f"  warning: {pdf} missing; run scripts.generate_policy_docs first")
                continue
            key = f"policies/{pid}.pdf"
            spaces.upload(key, pdf.read_bytes(), "application/pdf")
            cur.execute("UPDATE policy_products SET wording_key = %s WHERE id = %s", (key, pid))

        new_keys: set[str] = set()
        manifest = data_dir / "documents_manifest.csv"
        if not skip_documents and manifest.exists():
            rows = []
            with manifest.open(newline="") as f:
                for r in csv.DictReader(f):
                    data = (data_dir / "documents" / r["filename"]).read_bytes()
                    key = f"claims/{r['claim_id']}/{uuid.uuid5(DOC_NAMESPACE, r['claim_id'] + '/' + r['filename'])}.pdf"
                    spaces.upload(key, data, "application/pdf")
                    new_keys.add(key)
                    rows.append(
                        (
                            r["claim_id"],
                            r["doc_type"],
                            key,
                            r["filename"],
                            "application/pdf",
                            hashlib.sha256(data).hexdigest(),
                            page1_phash(data),
                            pdf_pages(data),
                            "pending",
                        )
                    )
            cur.executemany(
                "INSERT INTO claim_documents (claim_id, doc_type, storage_key, filename, content_type, sha256, phash, "
                "pages, parse_status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                rows,
            )
            cur.execute("SELECT count(*) FROM claim_documents")
            counts["claim_documents"] = cur.fetchone()[0]
        conn.commit()
        conn.autocommit = True
        for table in tables:
            cur.execute(f"ANALYZE {table}")

    for key in old_keys - new_keys:  # files of documents that no longer exist
        try:
            spaces.delete(key)
        except Exception as exc:  # noqa: BLE001 - best-effort cleanup only
            print(f"  warning: could not delete {key}: {exc}")
    counts["_seconds"] = round(time.perf_counter() - t0, 2)
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--skip-documents", action="store_true")
    a = ap.parse_args(argv)
    if not (a.data / "claims.csv").exists():
        print(f"{a.data}/claims.csv not found; run `uv run python -m scripts.generate_data` first", file=sys.stderr)
        return 1
    counts = load(a.data, a.skip_documents)
    secs = counts.pop("_seconds")
    for t, n in counts.items():
        print(f"  {t:<18}{n:>10,}")
    print(f"loaded in {secs}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
