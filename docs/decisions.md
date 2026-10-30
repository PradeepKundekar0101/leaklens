# Decisions

Choices made where the plan was ambiguous, or where the environment forced a deviation.
Each entry says what was chosen and why.

## Environment

- **Local-first build.** Today's build runs against local Postgres 17 + pgvector 0.8 (Homebrew), not DO Managed Postgres.
  Switching is only a change of `DATABASE_URL` / `DATABASE_URL_DIRECT`.
  `infra/app-spec.yaml` and `backend/Dockerfile` are written for the later DO deploy.
- **Storage backend switch.** `STORAGE_BACKEND=local|spaces`.
  `local` writes under `data/storage/` with the same `upload / download / presign / delete` interface.
  Local presigned URLs are 5-minute signed tokens served by `GET /api/v1/files/{token}`.
- **LLM and embeddings degrade gracefully.** With no `ANTHROPIC_API_KEY`, every LLM step returns "unavailable" and the pipeline uses deterministic fallbacks (templated explanations, rule-based coverage verdicts marked `needs_review`, no investigation report).
  With no `VOYAGE_API_KEY`, policy embeddings use a deterministic local hashing embedder (`local-hash-1024`) so hybrid search still runs; real Voyage vectors replace them when the key is set and policies are re-ingested.
- **Models.** `MODEL_REASONING=claude-sonnet-5-5`, `MODEL_FAST=claude-haiku-5-5` as the plan specifies; both are environment variables.

## Domain contract (shared by the data generator, rules engine and payable calculator)

### Line-item categories

`room`, `icu`, `nursing`, `ot`, `surgeon`, `pharmacy`, `consumables`, `investigations`, `implants`.

- The room line has `item_code = "ROOM"`, `qty = los` (days in a ward room), `unit_price = room_rent_per_day`.
- The ICU line (only some procedures) has `item_code = "ICU"`, `qty = icu days`, `unit_price = icu rent per day`.
- `nursing`, `ot`, `surgeon` lines have `item_code` `NURSING`, `OT`, `SURGEON` (service codes, not in `items.csv`).
- `pharmacy`, `consumables`, `investigations`, `implants` lines reference `items.csv` codes and carry an MRP.

### Policy parameters

- `room_rent_cap_pct` and `icu_cap_pct` are percent of sum insured **per day** (e.g. 1.0 means 1% of SI per day). `null` means no cap.
- `sub_limits` maps a procedure code to a rupee limit on the claim's payable amount for that procedure (string decimal).
- `waiting_periods = {"initial_days": 30, "listed_conditions_months": 24, "pre_existing_months": 36, "listed_procedures": [codes]}`.
  - Initial waiting: admission within `initial_days` of `start_date` (accidents excluded; no accident procedures are generated).
  - Listed conditions: procedure in `listed_procedures` and admission within `listed_conditions_months` of `start_date`.
  - Pre-existing: claim `diagnosis_code` is in the member's `declared_conditions` and admission within `pre_existing_months`.
- `copay_pct` and `deductible` are the member's share, **not leakage**.
- `clause_refs` maps each parameter name to its clause number in the wording, e.g. `{"room_rent_cap_pct": "4.2"}`.

### Rules (all money is `Decimal`, rounded to 2 places at the end of each step)

- **R01 room rent above cap.** `cap = SI × room_rent_cap_pct / 100`. If `rent > cap`: excess rent `= (rent − cap) × qty`, plus proportional deduction on **associated charges** (`nursing`, `ot`, `surgeon`) `= amount × (1 − cap / rent)`. Pharmacy, consumables, implants, investigations and ICU are excluded (IRDAI guidance).
- **R02 ICU rent above ICU cap.** Same formula on the ICU line, proportional deduction also on `nursing`, `ot`, `surgeon` only when R01 did not already apply (the larger ratio wins; never deduct twice).
- **R03 above contracted tariff.** Applies only when the provider has a tariff for the procedure. Procedure charges `= sum(ot + surgeon)`. Excess `= max(0, procedure charges − package_rate)`.
- **R04 item above MRP.** Excess `= (unit_price − mrp) × qty` for items with an MRP.
- **R05 non-payable item.** Full item amount for items flagged `non_payable`.
- **R06 waiting period.** Full claim, severity high.
- **R07 sub-limit exceeded.** Excess of the running payable over the procedure's sub-limit.
- **R08 exact duplicate.** Another claim with the same member policy, provider, admission date and claimed amount, created earlier. Full claim.
- **R09 service date outside admission-discharge.** Full item amount.
- **R10 exceeds remaining sum insured.** `remaining = member_policies.balance` (remaining SI at the start of the test period). Excess of payable over remaining.
- **R11 reused document.** Same SHA-256 or perceptual-hash distance ≤ 5 against another claim's document. No rupee impact on its own; it forces `refer_siu`.

### Leakage

`leakage = claimed − payable − member_share`, i.e. the sum of rule deductions (and verified `not_payable` coverage exclusions, and any excess over remaining SI).
The member's co-pay and deductible are reported separately as `member_share`, so clean claims show zero leakage.
For R06 and R08 (full-claim findings) the payable is 0 and the whole claimed amount is leakage.

## Rules and orchestration

- **Reused-document check (R11).** A perceptual hash at Hamming distance ≤ 5 cannot tell apart two digital bills printed from the same hospital template, so it would flag look-alike bills as reused.
  When both documents have extractable text, a phash match also requires identical normalised text; image-only (scanned) documents match on the perceptual hash alone; identical SHA-256 always matches.
- **Action policy gap.** The plan's table does not cover "no rule findings, medium risk"; it maps to `investigate`.
  Mapping it to `approve` auto-approved most planted anomaly claims (inflated pharmacy, pre-auth escalation, stretched stay sit mostly in the medium tier) while medium covers only ~1% of clean claims.
  The investigator agent still runs only for high risk.
  A reused document (R11) is treated like a duplicate and maps to `refer_siu`.
- **Coverage exclusions vs. parallel rules.** Rules and coverage run in parallel, so verified `not_payable` verdicts (confidence ≥ 0.7) are applied by recomputing the payable in the `join` node.
- **Re-processing** a claim deletes its LangGraph thread and previous analysis rows, then runs a fresh thread `claim:{id}`.
- **Copilot memory** is kept in the LangGraph store under `("copilot", "copilot:{claim}:{user}")` rather than as a checkpointed graph, because the copilot is a single streaming tool loop.
- **Evaluation code lives in `backend/evaluation/`**, outside `app/`, and a test asserts no module under `app/` mentions `ground_truth`.
- **Login email** is a normalised plain string, not `EmailStr`: internal `.local` addresses are valid accounts here.

## Synthetic data

- **Single source for products.** `data/policies/products.json` defines SILVER / GOLD / PLATINUM; `generate_data.py` writes `policy_products.csv` / `policy_params.csv` from it and `generate_policy_docs.py` renders the wordings from it, so values cannot drift.
- **clause_refs keys.** Besides every parameter name, `clause_refs` maps `sum_insured` (2.2), `non_payable` (3.14), `proportional_deduction` (4.4), `mrp` (4.5), `tariff` (4.6), `waiting_periods` (5.1), `listed_procedures` (5.3), `sub_limits` (6.1), `sub_limits.<code>` (6.2 onwards), `claims_procedure` (8.1) and `fraud` (9.5); the fixed numbering lives in `backend/scripts/datagen/common.py`.
- **PLATINUM has no room or ICU cap** (`null`), so `room_rent_above_cap` is planted only on SILVER and GOLD claims.
- **Room line quantity is ward days** (`los - icu_days`); the ICU line carries the ICU days and the nursing line carries `los`.
- **Claimed amount is built bottom-up.** Category targets follow the plan's recipe (expected cost x lognormal(0, 0.18), Beta pharmacy share), line items are quantised to integer quantities and 2-decimal unit prices, and `claimed_amount` is their exact sum, so every line satisfies `amount = qty x unit_price` without a fudged last line.
- **Plausible quantities.** `items.csv` carries `qty_fixed` and `qty_per_day`, and a line never exceeds `qty_fixed + qty_per_day x LOS`.
- Because of those caps the realised pharmacy share (surgical about 6-8%, medical about 16-26%) sits below `typical_pharmacy_share`; the 30-45% inflated-pharmacy anomaly stays clearly separated.
- **Reference size.** `items.csv` has 110 items rather than about 60, so each procedure has a realistic drug, consumable and investigation pool; the extra CSV columns (`tags`, `qty_fixed`, `qty_per_day`, and in `procedures.csv` `icu_days_typical`, `gender`, `template`, `implant_item`, `source`) are ignored by the loader.
- The `procedures` and `multipliers` tables have no `source` column, so their source text lives only in the CSVs.
- **MRP headroom.** Clean items are billed at 55-65% of MRP (so the 1.35-1.5x over-billing stays at or below MRP; inflated prices are also capped at MRP).
- **Tariffs.** Package rates cover OT + surgeon and are 1.55-1.80x the provider's typical procedure charges; clean network claims above 98% of the package (6.3%) are scaled to 85-97% of it.
- **One rule per rule scenario.** Scenario claims exclude product x procedure combinations with a sub-limit, and over-billing claims on such combinations are scaled to stay under the sub-limit, so each rule scenario triggers exactly its own rule.
- **Policy assignment** honours all waiting periods (with 21 days of slack for later date shifts), sum-insured eligibility (base rate at most 45% of SI), a per-policy budget (sum of base rates at most 60% of SI) and at most 4 claims per policy.
- Claims that would still trigger R07 or R10 are dropped (257, about 0.8%), so the default run has 29,894 train and 3,024 test claims (duplicates and reused-document clones included) instead of exactly 30,000 / 3,000.
- **Balance.** `member_policies.balance` = SI minus the claimed amounts of the policy's train claims (exact duplicates excluded); every claim in both splits fits within it, so R10 never fires on an unplanted claim.
- **Ground truth amounts.** Rule scenarios record `claimed - payable - member_share` per the contract; a cross-check against `app.services.rules` gave 100% recall and zero amount mismatches on both splits, and no findings on clean or anomaly claims apart from R11.
- Anomaly scenarios record the claim's total minus its own pre-transform total; `early_claim`, `reused_document` and `exact_duplicate` record the full claimed amount.
- **Reused documents.** 10 pairs in the test split, following the plan's scenario table rather than the single pair in the task prompt: 6 exact copies (same SHA-256) and 4 high-resolution re-scans (pHash match).
- The original claim of each reused pair has no ground-truth row.
- **Perceptual hash.** `claim_documents.phash` is `imagehash.phash(page1, hash_size=11)` (121 bits, 31 hex characters) at 100 dpi, because 64-bit pHash put about 360 unrelated same-template document pairs within distance 5.
- Even at 121 bits, 9 unrelated document pairs (mostly discharge summaries from the same layout) sit at distance 4 and re-scans land at 0-4, so a page-level pHash threshold cannot fully separate them; R11 currently flags 3 unplanted test claims.
- **Early claims.** Admission is 31-45 days after a policy that started in 2026 (10% of policies start between January and mid-September 2026); availability of eligible new policies makes them about 0.41% of claims instead of 0.5%.
- **Dates.** Test admissions are shifted so discharge is on or before 2026-10-28, and `created_at` is capped at 2026-10-30 18:00 UTC.
- **Reproducibility.** `policy_params.approved_at` is a fixed timestamp in the CSV so output is byte-identical per seed; `load_data` stamps `now()`.
- **Loader.** Storage keys are deterministic (`uuid5` of claim and filename) so reloads overwrite instead of orphaning files, and stale keys are deleted.
- The loader sets `lock_timeout = 15s` and, if the API or worker holds locks, exits with the blocking sessions listed instead of deadlocking.

## LLM integration

- **Structured outputs use lists, not maps.** Strict JSON-schema outputs require `additionalProperties: false`, so free-form maps (`sub_limits`, `clause_refs`) are returned as lists of objects and converted in code.
- **Token floor and effort.** Current models think adaptively and thinking counts against `max_tokens`, so structured calls use at least 4,000 tokens and the fast model runs at low effort for classification and extraction.
- **Explicit `ANTHROPIC_BASE_URL` setting** (default `https://api.anthropic.com`), so an inherited shell variable never redirects traffic.
- **Embedding rate limits.** Voyage requests are batched under 8K estimated tokens and retried with backoff on 429s; query embeddings are cached in-process.
- **Clause-note namespaces** encode clause numbers (`4.2` -> `4_2`) because store namespace labels cannot contain periods.

## Deployment

- **Spaces bucket in SGP1, not BLR1.** Spaces was not available in BLR1 for this account, so the bucket `leaklens-files` is in Singapore; Postgres stays in BLR1.
  This departs from the plan's fixed decision (and the data-residency item in Phase 10): claim documents and model files are stored outside India. Revisit before handling real claims.
- **Bulk batches run deterministically by default** (`use_llm: false`): rules, anomaly scoring and a templated explanation, no coverage, investigator or decision-writer calls.
  Single-claim processing, demo claims and live claims use every agent. Running the agents across thousands of claims is slow (Voyage rate limits) and costly; pass `use_llm: true` to `POST /admin/process-batch` to override.
- **Migrations use the direct database URL**; the API uses DO's PgBouncer pool in transaction mode (prepared statements disabled), and LangGraph uses the direct URL.
- **Deployed demo accounts use a generated password** (not the local seed password, which is public in this repository).
- **Job leases.** App Platform runs the old and new instance side by side during a deploy, so "re-queue running jobs at startup" let two instances process the same batch.
  Running jobs now refresh `heartbeat_at` every 20 s; only jobs silent for 90 s are re-queued, and a worker can only record a result while it still holds the lease (same attempt number).
- **Alembic ignores LangGraph's tables** (`checkpoints*`, `store*`); autogenerate otherwise proposes dropping them.
