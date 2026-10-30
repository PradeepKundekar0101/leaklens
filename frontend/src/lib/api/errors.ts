/** Error raised for any non-2xx API response. Body shape: {"error": {"code", "message"}}. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

const FALLBACK_MESSAGES: Record<number, string> = {
  401: "Your session has ended. Sign in again.",
  403: "Your role does not have access to this.",
  404: "Not found.",
  429: "Too many attempts. Wait a minute and try again.",
  500: "The server hit an error. Try again, and contact an admin if it keeps happening.",
  502: "The LeakLens server is not reachable. Check that the backend is running.",
  503: "The LeakLens server is temporarily unavailable.",
  504: "The LeakLens server did not respond in time.",
};

function readErrorBody(body: unknown): { code?: string; message?: string } {
  if (body && typeof body === "object" && "error" in body) {
    const inner = (body as { error: unknown }).error;
    if (inner && typeof inner === "object") {
      const { code, message } = inner as { code?: unknown; message?: unknown };
      return {
        code: typeof code === "string" ? code : undefined,
        message: typeof message === "string" ? message : undefined,
      };
    }
  }
  return {};
}

/** Builds an ApiError from an openapi-fetch error body and its Response. */
export function toApiError(body: unknown, response: Response): ApiError {
  const { code, message } = readErrorBody(body);
  return new ApiError(
    response.status,
    code ?? "error",
    message ?? FALLBACK_MESSAGES[response.status] ?? `Request failed (${response.status}).`,
  );
}

/**
 * Unwraps an openapi-fetch result: returns `data` or throws ApiError.
 *
 *   const user = unwrap(await api.GET("/api/v1/auth/me"));
 */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.response.ok && result.error === undefined) {
    return result.data as T;
  }
  throw toApiError(result.error, result.response);
}

/** A human-readable message for any thrown value. */
export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof TypeError) {
    return "Could not reach the LeakLens server. Check your connection and that the backend is running.";
  }
  if (error instanceof Error && error.message) return error.message;
  return "Something went wrong.";
}

export function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}
