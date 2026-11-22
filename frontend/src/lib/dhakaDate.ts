/**
 * Today's date in Asia/Dhaka. Pure functions (no imports) so `node --test`
 * can load this file directly; see tests/dhakaDate.test.mjs.
 */

export const DHAKA_TIME_ZONE = "Asia/Dhaka";

/** "Monday, 23 November" (en) or "সোমবার, ২৩ নভেম্বর" (bn), in Dhaka time. */
export function dhakaDateLabel(now: Date, language: "en" | "bn"): string {
  return new Intl.DateTimeFormat(language === "bn" ? "bn-BD" : "en-GB", {
    timeZone: DHAKA_TIME_ZONE,
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(now);
}

export type DayPart = "morning" | "afternoon" | "evening";

/** Greeting period from the hour in Dhaka: before 12, before 17, otherwise evening. */
export function dhakaDayPart(now: Date): DayPart {
  const hour = Number(
    new Intl.DateTimeFormat("en-GB", { timeZone: DHAKA_TIME_ZONE, hour: "numeric", hourCycle: "h23" }).format(now),
  );
  if (hour < 12) return "morning";
  if (hour < 17) return "afternoon";
  return "evening";
}
