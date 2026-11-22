import { NextResponse, type NextRequest } from "next/server";
import { routeDecision, type Viewer } from "@/lib/routeAccess";

/*
 * Server-side portal guard: /lawyer/* needs a lawyer session and /client/* a
 * client session (pages, route handlers and server actions alike). The role
 * comes from the backend (/api/v1/me), never from the browser.
 */

const SESSION_COOKIE = "lc_session";
const MOCK_PREFIX = "mock.";
const BACKEND_URL = process.env.BACKEND_API_URL ?? "http://127.0.0.1:8000";
const PASSWORD_CHANGE_REQUIRED = "PASSWORD_CHANGE_REQUIRED";

type Resolved = Viewer | "unknown";

async function resolveViewer(token: string | undefined): Promise<Resolved> {
  if (!token) return null;
  if (token.startsWith(MOCK_PREFIX)) {
    const mockAllowed = process.env.NODE_ENV !== "production" && process.env.MOCK_AUTH === "true";
    const role = token.slice(MOCK_PREFIX.length);
    return mockAllowed && (role === "lawyer" || role === "client")
      ? { role, passwordChangeRequired: false }
      : null;
  }
  let response: Response;
  try {
    response = await fetch(`${BACKEND_URL}/api/v1/me`, {
      headers: { Accept: "application/json", Cookie: `${SESSION_COOKIE}=${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
  } catch {
    return "unknown"; // backend unreachable: the layouts' session check still applies
  }
  if (response.status === 403) {
    const problem = (await response.json().catch(() => ({}))) as { detail?: unknown };
    if (typeof problem.detail === "string" && problem.detail.startsWith(PASSWORD_CHANGE_REQUIRED)) {
      return { role: "client", passwordChangeRequired: true };
    }
    return null;
  }
  if (!response.ok) return response.status >= 500 ? "unknown" : null;
  const user = (await response.json()) as { role?: string };
  if (user.role === "lawyer" || user.role === "client") return { role: user.role, passwordChangeRequired: false };
  return null;
}

export async function proxy(request: NextRequest) {
  const viewer = await resolveViewer(request.cookies.get(SESSION_COOKIE)?.value);
  if (viewer === "unknown") return NextResponse.next();
  const decision = routeDecision(request.nextUrl.pathname, viewer);
  if (decision.action === "next") return NextResponse.next();
  return NextResponse.redirect(new URL(decision.to, request.url));
}

export const config = {
  matcher: ["/lawyer/:path*", "/client/:path*"],
};
