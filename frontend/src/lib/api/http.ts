import { toApiError } from "./errors";

/**
 * Raw request helper for the few calls the typed client cannot model well:
 * multipart uploads and endpoints whose OpenAPI response is an untyped dict.
 * Same-origin relative URLs; the session cookie rides along.
 */
export async function apiRequest<T>(
  path: string,
  { method = "GET", query, json, form }: {
    method?: "GET" | "POST";
    query?: Record<string, string | number | boolean | null | undefined>;
    json?: unknown;
    form?: FormData;
  } = {},
): Promise<T> {
  const response = await fetch(withQuery(path, query), {
    method,
    credentials: "include",
    headers: json !== undefined ? { "Content-Type": "application/json", Accept: "application/json" } : { Accept: "application/json" },
    body: form ?? (json !== undefined ? JSON.stringify(json) : undefined),
  });
  const text = await response.text();
  let body: unknown = undefined;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }
  if (!response.ok) throw toApiError(body, response);
  return body as T;
}

export function withQuery(path: string, query?: Record<string, string | number | boolean | null | undefined>): string {
  if (!query) return path;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}
