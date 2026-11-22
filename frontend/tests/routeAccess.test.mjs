// Security: /lawyer/* requires the lawyer role and /client/* the client role (src/proxy.ts).
import assert from "node:assert/strict";
import { test } from "node:test";
import { routeDecision } from "../src/lib/routeAccess.ts";

const lawyer = { role: "lawyer", passwordChangeRequired: false };
const client = { role: "client", passwordChangeRequired: false };

test("a client session cannot open lawyer pages, route handlers or actions", () => {
  for (const path of ["/lawyer/dashboard", "/lawyer/matters/abc", "/lawyer/matters/abc/hearings/h/summary/pdf", "/lawyer"]) {
    assert.deepEqual(routeDecision(path, client), { action: "redirect", to: "/client/dashboard" }, path);
  }
});

test("a lawyer session cannot open client pages or downloads", () => {
  for (const path of ["/client/dashboard", "/client/summaries/s1", "/client/documents/d1/download", "/client/set-password"]) {
    assert.deepEqual(routeDecision(path, lawyer), { action: "redirect", to: "/lawyer/dashboard" }, path);
  }
});

test("each portal opens for its own role", () => {
  assert.deepEqual(routeDecision("/lawyer/matters", lawyer), { action: "next" });
  assert.deepEqual(routeDecision("/client/dashboard/", client), { action: "next" });
});

test("no session goes to that portal's login; login pages stay public", () => {
  assert.deepEqual(routeDecision("/lawyer/settings", null), { action: "redirect", to: "/lawyer/login" });
  assert.deepEqual(routeDecision("/client/summaries/x/pdf", null), { action: "redirect", to: "/client/login" });
  for (const path of ["/lawyer/login", "/lawyer/signup", "/lawyer/forgot-password", "/client/login", "/client/accept"]) {
    assert.deepEqual(routeDecision(path, null), { action: "next" }, path);
    assert.deepEqual(routeDecision(path, path.startsWith("/lawyer") ? client : lawyer), { action: "next" }, path);
  }
  assert.deepEqual(routeDecision("/", null), { action: "next" });
});

test("a client with a temporary password can only open set-password", () => {
  const pending = { role: "client", passwordChangeRequired: true };
  assert.deepEqual(routeDecision("/client/set-password", pending), { action: "next" });
  assert.deepEqual(routeDecision("/client/dashboard", pending), { action: "redirect", to: "/client/set-password" });
  assert.deepEqual(routeDecision("/lawyer/dashboard", pending), { action: "redirect", to: "/client/set-password" });
});
