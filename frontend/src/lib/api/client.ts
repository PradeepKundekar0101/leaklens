import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

/**
 * Typed API client.
 *
 * The base URL is relative on purpose: Next.js rewrites `/api/*` and `/health` to the
 * FastAPI backend (see next.config.ts), so the `leaklens_session` cookie is always
 * first-party. This client is meant for the browser; relative URLs do not resolve on the
 * server.
 */
export const api = createClient<paths>({
  baseUrl: "",
  credentials: "include",
  headers: { Accept: "application/json" },
});

export type Schemas = components["schemas"];
