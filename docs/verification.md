# Verification (local run, 30 Oct 2026)

Environment: macOS, Postgres 17.9 + pgvector 0.8.7 (Homebrew), local storage backend.
First pass ran without API keys (deterministic fallbacks); the second pass, recorded in "With API keys" below, used Claude (`claude-sonnet-5-5`, `claude-haiku-5-5`), Voyage (`voyage-3.5`) and LangSmith.

## Automated tests

- Backend: `uv run pytest` - 85 tests (rules, payable calculator, anomaly statistics, guardrails, PII masking, action policy, citation verification, security and role coverage, read-only tools, job queue, orchestrator integration incl. restart-and-resume, document pipeline incl. prompt-injection canary and reused-bill detection, synthetic-data invariants).
- Frontend: `pnpm test` (66 vitest tests), `pnpm lint`, `pnpm typecheck`, `pnpm build`.
- Lint: `ruff check` and `ruff format --check` clean.

## Phase acceptance results

| Phase | Criterion | Result |
| --- | --- | --- |
| 0 | `/health` OK for database and storage | Pass on the deployed URL (Postgres 17.11 in BLR1, Spaces in SGP1) |
| 0 | Sidebar differs by role | Pass locally in the browser; on the deployed URL all four roles sign in and get role-correct API access (the deployed sidebar is not yet checked in a browser) |
| 0 | No cookie -> 401, wrong role -> 403 | Pass (tests, and against the deployed URL) |
| 0 | Migrations run cleanly on DO Postgres and on the local fallback | Pass (also run by the App Platform pre-deploy job) |
| 0 | Test job enqueued, processed and marked done | Pass (test, and on the deployed worker) |
| 1 | Generation < 60 s, loading < 2 min | 6.1 s and 11-16 s |
| 1 | Line items sum exactly; no out-of-stay dates except planted; same seed identical | Pass (tests) |
| 1 | Calibration 5-10% planted leakage | 6.81% |
| 1 | Policy PDFs contain every referenced clause | Pass (test; all 60 clause refs also resolve to ingested chunks) |
| 2 | Hand-computed unit tests incl. edge cases; worked payable claim | Pass |
| 2 | Rule-scenario recall ≥ 95% on test split | 100% (580/580 incl. reused documents) |
| 2 | Clean claims produce no rule findings | 0 of 2,225 |
| 2 | Rules on 3,000 test claims < 10 s | 0.16 s (plus ~1 s loading) |
| 3 | Training < 30 s | 1.3 s |
| 3 | Combined recall on combination scenario exceeds z-only | 20.0% vs 13.3% (equal 10% flag budget) |
| 3 | Over-billing providers disproportionately in top 100 | **Not met**: 1% of top-100 vs 3.9% of claims. Their uplift (~1.35×) is ~1.5-2 robust z per claim and is outranked by stronger planted signals. They are caught by the provider O/E index (Phase 9). |
| 3 | Detection code never reads `ground_truth` | Pass (test greps `app/`) |
| 4 | Planted rule claim -> approve_with_deductions with correct payable | Pass (531 deduction claims; payable equals the payable calculator; data cross-check matches leakage to the paisa) |
| 4 | Planted combination claim -> investigate / refer_siu | **Not met**: 13 of 15 combination claims score low risk (signals are deliberately mild). |
| 4 | Restart while pending_review, review still resumes | Pass (integration test) |
| 4 | Every stored explanation passes the number guardrail | Pass (test; template explanations only, no LLM key) |
| 4 | Full trace in LangSmith | Pass (one trace per claim run, tagged with claim, run, model and rules versions) |
| 5 | Review flow for an adjuster; auditor/manager cannot decide; peer histogram; Indian amounts | Pass (browser + API tests) |
| 6 | Sample PDFs extract with totals matching | Pass: 50/50 bills with Claude extraction (`python -m evaluation.extraction`); also passes via Docling tables without a key |
| 6 | Scanned samples via vision route | Pass: 7/7 scanned bills through the vision route with matching totals |
| 6 | Planted reused-image pair flagged | Pass (10/10 pairs, R11) |
| 6 | Non-PDF disguised as `.pdf` rejected | Pass (415) |
| 6 | Prompt-injection canary has no effect | Pass (test, deterministic path) |
| 7 | "room rent limit" returns the room-rent clause first | Pass (clause 4.2 for all three products) |
| 7 | Extracted parameters match `policy_params` exactly | Pass: 30/30 values across the three products, all returned clause references agree |
| 7 | Golden set (30 labelled line items) and public policy PDF | Not done: no hand-labelled golden set yet; no public policy PDF supplied in `data/policies/public/` |
| 7 | No unverified citation displayed as verified | Pass (verification unit test; UI shows verified state only when `verified=true`) |
| 8 | Investigator report cites ≥ 3 different tool results | Pass on high-risk claim C0029951 (peer distribution, similar cases, documents) |
| 8 | Override note appears in the coverage agent's context | Pass (API test: override note is returned by `get_clause_notes`) |
| 8 | Copilot answers "why was this flagged?" from stored findings | Pass (one `get_claim_state` call, all figures from stored results) |
| 8 | No tool can modify data | Pass (read-only transaction test + source check of every tool) |
| 9 | Over-billing providers rank top 2 by O/E index | Pass (H016 1.357, H005 1.347; next 1.166) |
| 9 | Dashboard totals reconcile with recommendations | Pass (test + live check) |
| 10 | Role check on every route | Pass (test enumerates routes) |
| 10 | `reset_demo` < 1 minute | Locally 2.7 s with deterministic processing. On DO with every Claude agent on the five demo claims: about 20 minutes, dominated by the Voyage free-tier rate limit |
| 10 | Backend image with Docling models, App Platform spec with `/health` check and migrations on deploy | Pass |
| 10 | Fresh deploy from `main` without manual steps | Partly: deploys build from the public repo over HTTPS, triggered by `doctl apps create-deployment` (no deploy-on-push without the GitHub integration) |
| 10 | LangSmith datasets, CI on GitHub, backup video | Not done |

## Detection evaluation (test split, model v20261030-134213)

Each method flags its top 10% of claims (302).

| Scenario | z-only | IF-only | combined |
| --- | --- | --- | --- |
| inflated_pharmacy | 100% | 73% | 100% |
| preauth_escalation | 93% | 53% | 93% |
| stretched_stay | 53% | 30% | 43% |
| combination | 13% | 20% | 20% |
| early_claim | 14% | 14% | 14% |
| overbilling_provider | 14% | 9% | 15% |
| precision@50 | 94% | 90% | 98% |
| precision@100 | 93% | 75% | 96% |

Actions on the 3,024 test claims: 2,350 approve, 532 approve with deductions, 94 investigate, 48 refer to SIU.

## With API keys

- Policies re-ingested with Voyage embeddings and Claude clause classification; "room rent limit" still returns clause 4.2 first for every product.
- Three claims processed end to end with every agent: C0029235 (non-payable items), C0029132 (room rent above cap) and C0029951 (high risk, investigator). No node errors.
- The coverage agent's non-payable verdicts all carried verified verbatim quotes. It also excluded a urine bag that the wording's annexure (clause 10.5) lists as non-payable but `items.csv` does not flag, which is a real inconsistency in the synthetic reference data.
- Decision explanations and copilot answers come from Claude and pass the number guardrail; prompts v2 ask for Indian digit grouping.

Bugs found and fixed in this pass:
- Small structured-output limits truncated JSON because current models think adaptively; the client now uses a 4,000-token floor, low effort for fast-model tasks, and retries SDK parse failures.
- Map-typed fields (`dict[str, ...]`) always came back empty under strict structured outputs; parameter extraction now uses lists.
- Agent tools that built their result after the read-only transaction ended failed with `DetachedInstanceError`; objects are now detached before rollback, and a test calls every tool.
- Clause-note memory used namespace labels like `4.2`, which LangGraph's store rejects; clause numbers are now encoded (`4_2`).
- An `ANTHROPIC_BASE_URL` inherited from the shell would have redirected API traffic; the base URL is now an explicit setting.

Open item: the Voyage account has no payment method, so it is limited to 3 requests and 10K tokens per minute.
Ingestion still completes (batching plus backoff, about 2.5 minutes per product), but a claim with coverage takes 3-6 minutes because each policy search waits for the rate limit.
Adding a payment method on the Voyage dashboard removes the bottleneck; bulk processing of the test split with all agents should wait until then.
