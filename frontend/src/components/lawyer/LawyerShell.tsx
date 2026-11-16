"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { signOut } from "@/app/actions";
import { Icon, type IconName } from "@/components/Icon";
import { LanguageToggle } from "@/components/LanguageToggle";
import { Logo } from "@/components/Logo";
import type { LawyerProfile } from "@/lib/api/lawyer";
import {
  dictionaries,
  numberFor,
  pick,
  type Language,
} from "@/lib/i18n";

type NavKey = "dashboard" | "matters" | "clients" | "settings";

const items: { key: NavKey; href: string; icon: IconName }[] = [
  { key: "dashboard", href: "/lawyer/dashboard", icon: "dashboard" },
  { key: "matters", href: "/lawyer/matters", icon: "briefcase" },
  { key: "clients", href: "/lawyer/clients", icon: "clients" },
  { key: "settings", href: "/lawyer/settings", icon: "settings" },
];

function initials(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export function LawyerShell({
  language,
  profile,
  matterCount,
  children,
}: {
  language: Language;
  profile: LawyerProfile;
  matterCount: number;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const copy = dictionaries[language];
  const common = copy.common;

  const isActive = (href: string) =>
    href === "/lawyer/dashboard" ? pathname === href : pathname.startsWith(href);

  return (
    <div className={`app-shell language-${language}`} lang={language}>
      <aside className="sidebar">
        <div className="sidebar-head">
          <Logo language={language} />
        </div>
        <div className="side-section-label">{copy.nav.workspace}</div>
        <nav aria-label={copy.nav.workspace}>
          {items.map((item) => {
            const active = isActive(item.href);
            return (
              <Link
                key={item.key}
                href={item.href}
                className={active ? "active" : ""}
                aria-current={active ? "page" : undefined}
              >
                <Icon name={item.icon} size={19} />
                {copy.nav[item.key]}
                {item.key === "matters" ? (
                  <small>{numberFor(language, matterCount)}</small>
                ) : null}
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-footer">
          <span>{pick(profile.firm, language)}</span>
          <small>{pick(profile.location, language)}</small>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div className="mobile-topbar-logo">
            <Logo language={language} />
          </div>
          <div className="topbar-right">
            <LanguageToggle language={language} compact />
            <div className="user-meta">
              <span className="avatar">{initials(profile.name.en)}</span>
              <span>
                <b>{pick(profile.name, language)}</b>
                <small>{common.advocate}</small>
              </span>
            </div>
            <form action={signOut}>
              <button className="icon-button" type="submit" aria-label={common.signOut}>
                <Icon name="logout" size={19} />
              </button>
            </form>
          </div>
        </header>
        <main className="main-content">{children}</main>
      </div>

      <nav className="bottom-nav" aria-label={copy.nav.workspace}>
        {items.map((item) => {
          const active = isActive(item.href);
          return (
            <Link
              key={item.key}
              href={item.href}
              className={active ? "active" : ""}
              aria-current={active ? "page" : undefined}
            >
              <Icon name={item.icon} size={20} />
              <span>{copy.nav[item.key]}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
