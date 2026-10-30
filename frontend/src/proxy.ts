import { NextResponse, type NextRequest } from "next/server";

export const SESSION_COOKIE = "leaklens_session";

/**
 * Optimistic auth check: without a session cookie, app routes redirect to /login before
 * any page renders. The cookie's validity is checked by the backend; an expired cookie
 * gets a 401 from /auth/me and the client-side guard in the app shell redirects then.
 */
export function proxy(request: NextRequest) {
  if (request.cookies.has(SESSION_COOKIE)) return NextResponse.next();
  const url = request.nextUrl.clone();
  const next = `${request.nextUrl.pathname}${request.nextUrl.search}`;
  url.pathname = "/login";
  url.search = next === "/" ? "" : `?next=${encodeURIComponent(next)}`;
  return NextResponse.redirect(url);
}

export const config = {
  // Everything except the login page, API/health rewrites, Next internals and static files.
  matcher: ["/((?!login|api/|health|_next/|favicon\\.ico|.*\\.[\\w]+$).*)"],
};
