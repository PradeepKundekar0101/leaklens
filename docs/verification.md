# Verification (local run, 30 Oct 2026)

Environment: macOS, Postgres 17.9 + pgvector 0.8.7 (Homebrew), local storage backend, no `ANTHROPIC_API_KEY` / `VOYAGE_API_KEY` (LLM steps use their deterministic fallbacks).

## Automated tests

- Backend: `uv run pytest` - 84 tests (rules, payable calculator, anomaly statistics, guardrails, PII masking, action policy, citation verification, security and role coverage, read-only tools, job queue, orchestrator integration incl. restart-and-resume, document pipeline incl. prompt-injection canary and reused-bill detection, synthetic-data invariants).
- Frontend: `pnpm test` (48 vitest tests), `pnpm lint`, `pnpm typecheck`, `pnpm build`.
- Lint: `ruff check` and `ruff format --check` clean.

## Phase acceptance results

| Phase | Criterion | Result |
| --- | --- | --- |
| 0 | `/health` OK for database and storage | Pass (local) |
| 0 | Sidebar differs by role | Pass (browser, all four roles) |
| 0 | No cookie -> 401, wrong role -> 403 | Pass (tests) |
| 0 | Migrations clean on local fallback | Pass; DO Postgres not provisioned |
| 0 | Test job enqueued, processed, done | Pass (test) |
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
| 4 | Full trace in LangSmith | Not verified (no LangSmith key) |
| 5 | Review flow for an adjuster; auditor/manager cannot decide; peer histogram; Indian amounts | Pass (browser + API tests) |
| 6 | Sample PDFs extract with totals matching | Pass for digital bills via Docling tables; LLM extraction not exercised (no key) |
| 6 | Scanned samples via vision route | Not verified (needs `ANTHROPIC_API_KEY`); without a key they are marked `needs_human` |
| 6 | Planted reused-image pair flagged | Pass (10/10 pairs, R11) |
| 6 | Non-PDF disguised as `.pdf` rejected | Pass (415) |
| 6 | Prompt-injection canary has no effect | Pass (test, deterministic path) |
| 7 | "room rent limit" returns the room-rent clause first | Pass (clause 4.2 for all three products) |
| 7 | Golden set, parameter extraction match, public PDF | Not verified (needs LLM key; no public policy PDF supplied in `data/policies/public/`) |
| 7 | No unverified citation displayed as verified | Pass (verification unit test; UI shows verified state only when `verified=true`) |
| 8 | Investigator, copilot, clause-note memory with real model | Not verified (needs LLM key); copilot fallback streams stored findings |
| 8 | No tool can modify data | Pass (read-only transaction test + source check of every tool) |
| 9 | Over-billing providers rank top 2 by O/E index | Pass (H016 1.357, H005 1.347; next 1.166) |
| 9 | Dashboard totals reconcile with recommendations | Pass (test + live check) |
| 10 | Role check on every route | Pass (test enumerates routes) |
| 10 | `reset_demo` < 1 minute | 2.7 s (rest of the test split re-processes in the background, ~2.5 min) |
| 10 | Deploy to DO, LangSmith datasets, backup video | Not done (local-only build by decision) |

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
