import { cookies } from "next/headers";
import type { Language } from "./i18n";

export async function getLanguage(): Promise<Language> {
  const store = await cookies();
  return store.get("lang")?.value === "bn" ? "bn" : "en";
}
