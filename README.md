# LeakLens

LeakLens checks every health-insurance claim before payment.
It reads the documents, applies the policy, scores how unusual the claim is, and recommends an action that a human adjuster confirms.

Code calculates money; LLMs interpret text; statistics judge normality; a human makes the final decision.

## Architecture

- **Frontend** (`frontend/`): Next.js App Router, TypeScript, Tailwind, shadcn/ui, TanStack Query, Recharts, typed client generated from the backend's OpenAPI.
  The browser talks only to Next.js, which proxies `/api` to the backend so the session cookie stays first-party.
- **Backend** (`backend/`): FastAPI, SQLAlchemy 2 (async, psycopg 3), Alembic, JWT in an httpOnly cookie, role dependency on every route.
- **Orchestrator** (`backend/app/agents/graph.py`): a LangGraph state graph per claim:
  `load_claim → document → load_policy → (rules | anomaly | coverage × N) → join → route → [investigate] → decide → human_review (interrupt) → finalize`.
  Checkpoints and memory live in Postgres (`AsyncPostgresSaver`, `AsyncPostgresStore`), so a claim paused for review survives restarts.
- **Deterministic services:** rules engine R01-R11 and payable calculator (`services/rules/`), anomaly scorer (robust z + Isolation Forest + SHAP, `services/anomaly/`).
- **Agents:** document (extraction + vision), coverage (quoted, verified clauses), investigator (8-tool budget), decision writer (explanation only, with a number guardrail), adjuster copilot (SSE).
- **Jobs:** a Postgres `jobs` table polled with `SELECT … FOR UPDATE SKIP LOCKED`, run by an asyncio worker in the API process.
- **Data:** Postgres + pgvector (relational data, embeddings, full-text search, LangGraph tables) and object storage (DO Spaces, or the local filesystem).

See `docs/decisions.md` for every choice made where the plan was ambiguous, including the shared domain contract (rule formulas, leakage definition).

## Quick start (local)

Requirements: Python 3.12 with `uv`, Node 24+ with `pnpm`, Postgres 17 with pgvector (`brew install pgvector`, or `docker compose -f infra/docker-compose.local.yml up -d`).

```bash
cp .env.example .env        # set DATABASE_URL / DATABASE_URL_DIRECT; add API keys when you have them
createdb leaklens
cd backend && uv sync && cd ../frontend && pnpm install && cd ..
make setup                  # migrate, seed users, generate + load data, train, ingest policies, reset demo
make dev                    # backend :8000, frontend :3000
```

Demo accounts (local seed only; override with `SEED_PASSWORD`): `adjuster@leaklens.local`, `auditor@leaklens.local`, `manager@leaklens.local`, `admin@leaklens.local`, password `LeakLens!2026`.

### Without API keys

Everything runs without `ANTHROPIC_API_KEY` / `VOYAGE_API_KEY`:
explanations fall back to a templated text built from the deterministic results, digital bills are extracted from Docling's tables, coverage and investigation are marked unavailable, and policy search uses a local hashing embedder.
Add the keys to `.env`, restart, and re-run `make ingest` to switch to Claude and Voyage.

## Make targets

| Target | What it does |
| --- | --- |
| `make migrate` | Alembic migrations (pgvector extension and all tables) |
| `make seed-users` | One user per role |
| `make generate` | Policy wording PDFs, ~30k train + ~3k test claims with planted leakage, sample bills |
| `make load` | Bulk `COPY` into Postgres, upload documents and wordings to storage |
| `make train` | Peer statistics + Isolation Forest, registered, activated, evaluated |
| `make evaluate` | Rules recall/precision and the anomaly comparison table on the test split |
| `make ingest` | Chunk, classify and embed policy wordings; extract parameters for approval |
| `make reset-demo` | Reset analysis state and pre-process the five hero claims |
| `make test` / `make lint` | Backend pytest + frontend vitest / ruff + ESLint + tsc |

## Status

All phases (0-10) are implemented locally.
Deployment to DigitalOcean is prepared (`backend/Dockerfile`, `infra/app-spec.yaml`, CI in `.github/workflows/ci.yml`) but not provisioned.
Results of the last local verification run are in `docs/verification.md`.
