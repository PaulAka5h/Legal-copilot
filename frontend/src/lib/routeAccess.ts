/**
 * Which portal a path belongs to and whether a viewer may open it. Pure (no
 * imports) so `node --test` can load it; src/proxy.ts applies it server-side
 * before any /lawyer/* or /client/* route renders. The backend still enforces
 * the role on every API call; this keeps pages, route handlers and server
 * actions of one portal away from the other portal's accounts.
 */

export type PortalRole = "lawyer" | "client";
export type Viewer = { role: PortalRole; passwordChangeRequired: boolean } | null;
export type Decision = { action: "next" } | { action: "redirect"; to: string };

const PUBLIC_PATHS = new Set([
  "/lawyer/login",
  "/lawyer/signup",
  "/lawyer/forgot-password",
  "/client/login",
  "/client/accept",
]);
const SET_PASSWORD = "/client/set-password";

export function portalOf(pathname: string): PortalRole | null {
  if (pathname === "/lawyer" || pathname.startsWith("/lawyer/")) return "lawyer";
  if (pathname === "/client" || pathname.startsWith("/client/")) return "client";
  return null;
}

export function dashboardFor(role: PortalRole): string {
  return role === "lawyer" ? "/lawyer/dashboard" : "/client/dashboard";
}

export function routeDecision(rawPathname: string, viewer: Viewer): Decision {
  const pathname = rawPathname.length > 1 ? rawPathname.replace(/\/+$/, "") : rawPathname;
  const portal = portalOf(pathname);
  if (!portal || PUBLIC_PATHS.has(pathname)) return { action: "next" };
  if (!viewer) return { action: "redirect", to: `/${portal}/login` };
  if (viewer.passwordChangeRequired) {
    return pathname === SET_PASSWORD ? { action: "next" } : { action: "redirect", to: SET_PASSWORD };
  }
  if (viewer.role !== portal) return { action: "redirect", to: dashboardFor(viewer.role) };
  return { action: "next" };
}
