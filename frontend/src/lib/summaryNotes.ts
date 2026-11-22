/**
 * Pure helpers for hearing summaries (no imports, so `node --test` can load
 * this file directly; see tests/summaryNotes.test.mjs).
 */

export type NoteLike = { id: string; text: string };
export type LocalizedText = { en: string; bn: string };

function noteKey(text: string) {
  return text.normalize("NFC").trim().replace(/\s+/g, " ").toLowerCase();
}

/**
 * The key notes of a hearing: its purpose and only the latest recorded update.
 * Hearing updates are append-only versions (a correction or a re-submission is
 * a new version), so earlier versions are history, not extra notes. Notes with
 * the same text are shown once.
 */
export function currentKeyNotes(purpose: NoteLike | null, updates: NoteLike[]): NoteLike[] {
  const latest = updates.length > 0 ? [updates[updates.length - 1]] : [];
  const seen = new Set<string>();
  return [...(purpose ? [purpose] : []), ...latest].filter((note) => {
    const key = noteKey(note.text);
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

/**
 * Apply an edit made in one language. When the other language still holds the
 * same untranslated text, it is replaced too; otherwise the viewer switching
 * language would keep seeing the old text.
 */
export function editLocalized(
  current: LocalizedText,
  language: "en" | "bn",
  value: string,
): LocalizedText {
  if (current.en === current.bn) return { en: value, bn: value };
  return { ...current, [language]: value };
}
