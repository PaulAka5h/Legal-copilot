import { NextResponse } from "next/server";
import { SESSION_COOKIE } from "@/lib/api/backendClient";
import { clearSession, getSession } from "@/lib/session";

/**
 * GET /logout: always signs out, even when no dashboard can load. Ends the
 * backend session, clears the cookie and goes to the matching login page.
 */
export async function GET(request: Request) {
  const session = await getSession().catch(() => null);
  await clearSession();

  const destination = !session ? "/" : session.role === "client" ? "/client/login" : "/lawyer/login";
  const response = NextResponse.redirect(new URL(destination, request.url), 303);
  response.cookies.set(SESSION_COOKIE, "", { httpOnly: true, maxAge: 0, path: "/", sameSite: "lax" });
  response.headers.set("Cache-Control", "no-store");
  return response;
}
