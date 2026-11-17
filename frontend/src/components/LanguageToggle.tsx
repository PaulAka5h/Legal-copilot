import { setLanguage } from "@/app/actions";
import { dictionaries, type Language } from "@/lib/i18n";

export function LanguageToggle({
  language,
  compact = false,
}: {
  language: Language;
  compact?: boolean;
}) {
  const copy = dictionaries[language].common;

  return (
    <form action={setLanguage} className={`language-pill ${compact ? "compact" : ""}`}>
      <button
        type="submit"
        name="language"
        value="en"
        className={language === "en" ? "active" : ""}
        aria-pressed={language === "en"}
      >
        {copy.languageEn}
      </button>
      <span aria-hidden="true">|</span>
      <button
        type="submit"
        name="language"
        value="bn"
        className={language === "bn" ? "active" : ""}
        aria-pressed={language === "bn"}
      >
        {copy.languageBn}
      </button>
    </form>
  );
}
