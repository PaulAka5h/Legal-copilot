import { dictionaries, type Language } from "@/lib/i18n";

export function Logo({ language, light = false }: { language: Language; light?: boolean }) {
  const copy = dictionaries[language].brand;

  return (
    <span className={`logo ${light ? "logo-light" : ""}`}>
      <span className="logo-mark">
        <span>LC</span>
      </span>
      <span className="logo-copy">
        <b>{copy.name}</b>
        <small>{copy.tagline}</small>
      </span>
    </span>
  );
}
