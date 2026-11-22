import "server-only";

import { BackendError, backend, withDemoFallback } from "@/lib/api/backendClient";
import type { ProfileInput } from "@/lib/api/lawyerTypes";
import { PRACTICE_AREAS, SPOKEN_LANGUAGES, VISIBLE_FIELDS } from "@/lib/api/lawyerTypes";

/*
 * Profile validation and photo upload. The backend validates again (and is the
 * authority); these checks give the lawyer a quick error without a round trip.
 */

export const MAX_PHOTO_BYTES = 5 * 1024 * 1024;
const PHOTO_URL = "/api/v1/lawyer/profile/photo";
const BD_MOBILE = /^(?:\+?880|0)?(1[3-9]\d{8})$/;
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Bangla often arrives decomposed; lengths are counted on the NFC form, like the backend. */
export function nfc(value: string): string {
  return value.normalize("NFC").trim();
}

/** "+8801712345678", "01712345678" (spaces/dashes allowed) -> "+8801712345678"; null if not a BD mobile. */
export function normalizeBdPhone(value: string): string | null {
  const match = BD_MOBILE.exec(value.replace(/[\s\-()]/g, ""));
  return match ? `+880${match[1]}` : null;
}

function within(value: string, max: number) {
  return nfc(value).length <= max;
}

export function isValidProfileInput(input: ProfileInput, canEditOrganization: boolean): boolean {
  const fullName = nfc(input.fullName);
  const phone = input.phone.trim();
  const checks = [
    fullName.length > 0 && fullName.length <= 200,
    phone.length <= 30 && /^[0-9+()\- ]*$/.test(phone),
    within(input.chamberName, 200),
    !canEditOrganization || nfc(input.organizationName).length > 0,
    within(input.organizationName, 200),
    within(input.barEnrollmentNo, 50),
    input.courts.length <= 10 && input.courts.every((court) => within(court, 150)),
    input.practiceAreas.every((area) => PRACTICE_AREAS.includes(area)),
    input.languages.every((language) => SPOKEN_LANGUAGES.includes(language)),
    input.visibleFields.every((field) => VISIBLE_FIELDS.includes(field)),
    input.yearsExperience === null ||
      (Number.isInteger(input.yearsExperience) && input.yearsExperience >= 0 && input.yearsExperience <= 80),
    within(input.officeAddress, 300),
    within(input.bio, 500),
    !input.publicPhone.trim() || normalizeBdPhone(input.publicPhone) !== null,
    !input.publicEmail.trim() || (input.publicEmail.trim().length <= 254 && EMAIL.test(input.publicEmail.trim())),
  ];
  return checks.every(Boolean);
}

export type PhotoResult =
  | "saved" | "removed" | "too_large" | "wrong_type" | "invalid" | "rate_limited" | "error" | "NOT_CONFIGURED";

const PHOTO_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

/** Upload or replace the photo. The backend checks the real type from the bytes. */
export async function uploadProfilePhoto(file: File): Promise<PhotoResult> {
  if (file.size === 0) return "invalid";
  if (file.size > MAX_PHOTO_BYTES) return "too_large";
  if (file.type && !PHOTO_TYPES.has(file.type)) return "wrong_type";
  const form = new FormData();
  form.append("file", file, file.name || "photo");
  return withDemoFallback<PhotoResult>(
    async () => {
      try {
        await backend(PHOTO_URL, { method: "PUT", form });
        return "saved";
      } catch (error) {
        if (!(error instanceof BackendError)) throw error;
        if (error.status === 413) return "too_large";
        if (error.status === 415) return "wrong_type";
        if (error.status === 422) return "invalid";
        if (error.status === 429) return "rate_limited";
        return error.status === 503 ? "NOT_CONFIGURED" : "error";
      }
    },
    () => "NOT_CONFIGURED",
  );
}

export async function removeProfilePhoto(): Promise<PhotoResult> {
  return withDemoFallback<PhotoResult>(
    async () => {
      try {
        await backend(PHOTO_URL, { method: "DELETE" });
        return "removed";
      } catch (error) {
        if (!(error instanceof BackendError)) throw error;
        if (error.status === 429) return "rate_limited";
        return error.status === 503 ? "NOT_CONFIGURED" : "error";
      }
    },
    () => "NOT_CONFIGURED",
  );
}
