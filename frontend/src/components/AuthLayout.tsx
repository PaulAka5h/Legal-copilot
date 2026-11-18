import type { ReactNode } from "react";
import { dictionaries, type Language } from "@/lib/i18n";
import { Icon } from "./Icon";
import { LanguageToggle } from "./LanguageToggle";
import { Logo } from "./Logo";

export function AuthLayout({
  type,
  language,
  children,
  switcher,
}: {
  type: "lawyer" | "client";
  language: Language;
  children: ReactNode;
  switcher?: ReactNode;
}) {
  const copy = dictionaries[language][type];

  return (
    <div className={`auth-page language-${language}`} lang={language}>
      <aside className="auth-brand">
        <Logo language={language} light />
        <div className="brand-message">
          <span className="eyebrow light">{copy.builtFor}</span>
          <h1>
            {copy.headline1}
            <br />
            {copy.headline2}
          </h1>
          <p>{copy.brandCopy}</p>
        </div>
        <div className="trust-note">
          <Icon name="lock" size={17} />
          {dictionaries[language].common.privateSecure}
        </div>
      </aside>
      <section className="auth-form-side">
        <div className="mobile-auth-logo">
          <Logo language={language} />
        </div>
        <LanguageToggle language={language} />
        <div className="auth-card">
          {children}
          {switcher ? <div className="auth-switch">{switcher}</div> : null}
        </div>
      </section>
    </div>
  );
}
