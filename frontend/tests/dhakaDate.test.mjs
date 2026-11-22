// Bug 6: the dashboard date was hard-coded to "Tuesday, 14 January".
import assert from "node:assert/strict";
import { test } from "node:test";
import { dhakaDateLabel, dhakaDayPart } from "../src/lib/dhakaDate.ts";

test("formats the given instant in Asia/Dhaka, in English and Bangla", () => {
  // 2026-11-23 20:30 UTC is already Tuesday 24 November in Dhaka (UTC+6).
  const instant = new Date("2026-11-23T20:30:00Z");
  // Punctuation varies between ICU versions; the parts must not.
  const en = dhakaDateLabel(instant, "en");
  const bn = dhakaDateLabel(instant, "bn");
  for (const part of ["Tuesday", "24", "November"]) assert.ok(en.includes(part), en);
  for (const part of ["মঙ্গলবার", "২৪", "নভেম্বর"]) assert.ok(bn.includes(part), bn);
});

test("is computed from the date passed in, not a fixed value", () => {
  assert.notEqual(
    dhakaDateLabel(new Date("2026-01-14T06:00:00Z"), "en"),
    dhakaDateLabel(new Date("2026-11-23T06:00:00Z"), "en"),
  );
});

test("greeting period follows the Dhaka hour", () => {
  assert.equal(dhakaDayPart(new Date("2026-11-23T02:00:00Z")), "morning"); // 08:00 Dhaka
  assert.equal(dhakaDayPart(new Date("2026-11-23T08:00:00Z")), "afternoon"); // 14:00 Dhaka
  assert.equal(dhakaDayPart(new Date("2026-11-23T13:00:00Z")), "evening"); // 19:00 Dhaka
});
