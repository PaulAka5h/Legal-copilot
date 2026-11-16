import type { ReactNode } from "react";
import { signOut } from "@/app/actions";
import { Icon } from "@/components/Icon";
import { LanguageToggle } from "@/components/LanguageToggle";
import { Logo } from "@/components/Logo";
import type { ClientProfile } from "@/lib/api/client";
import { dictionaries, pick, type Language } from "@/lib/i18n";
import { initials } from "@/lib/initials";

export function ClientShell({
  language,
  profile,
  children,
}: {
  language: Language;
  profile: ClientProfile;
  children: ReactNode;
}) {
  const copy = dictionaries[language];

  return (
    <div className={`client-shell language-${language}`} lang={language}>
      <header className="topbar">
        <Logo language={language} />
        <div className="topbar-right">
          <LanguageToggle language={language} compact />
          <div className="user-meta">
            <span className="avatar">{initials(profile.name.en)}</span>
            <span>
              <b>{pick(profile.name, language)}</b>
              <small>{copy.common.client}</small>
            </span>
          </div>
          <form action={signOut}>
            <button className="icon-button" type="submit" aria-label={copy.common.signOut}>
              <Icon name="logout" size={19} />
            </button>
          </form>
        </div>
      </header>
      <main className="main-content">{children}</main>
    </div>
  );
}
