# LeakLens frontend

Next.js (App Router) client for the LeakLens claims-leakage auditor.

## Run

```bash
pnpm install
pnpm dev            # http://localhost:3000
```

The browser only talks to this app.
`/api/*` and `/health` are rewritten to the FastAPI backend at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`), so the `leaklens_session` cookie is first-party.
Set it in `frontend/.env.local` (Next reads env files from this directory, not the repo root), then restart the dev server.

In development the sign-in page shows one-click fills for the four seeded demo accounts.

## Scripts

| Script | What it does |
| --- | --- |
| `pnpm dev` | Dev server on port 3000 |
| `pnpm build` / `pnpm start` | Production build and server |
| `pnpm lint` | ESLint |
| `pnpm typecheck` | `tsc --noEmit` |
| `pnpm test` | Vitest unit tests |
| `pnpm gen:api` | Regenerate `src/lib/api/schema.d.ts` from the running backend's OpenAPI schema |

## Layout

- `src/app/login` - sign-in page.
- `src/app/(app)` - authenticated routes inside the app shell (`claims`, `claims/[id]`, `providers`, `dashboard`, `policies`, `audit`, `admin`).
- `src/proxy.ts` - redirects to `/login` when there is no session cookie.
- `src/components/app-shell` - sidebar, top bar, role-based navigation and the session guard.
- `src/components/status-badges.tsx` - risk and action badges.
- `src/lib/api` - typed `openapi-fetch` client and error helpers.
- `src/lib/auth` - `useMe`, `useLogin`, `useLogout`, roles.
- `src/lib/format.ts` - rupee (Indian grouping), number, percent and date formatting.
