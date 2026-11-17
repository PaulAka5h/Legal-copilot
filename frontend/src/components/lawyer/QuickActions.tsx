"use client";

import Link from "next/link";
import { useState } from "react";
import { Icon } from "@/components/Icon";
import { dictionaries, type Language } from "@/lib/i18n";

export function QuickActions({ language }: { language: Language }) {
  const [open, setOpen] = useState(false);
  const copy = dictionaries[language].dashboard;

  return (
    <div className="quick-wrap">
      {open ? (
        <div className="quick-menu" role="menu">
          <Link href="/lawyer/matters/new" role="menuitem">
            <span>
              <Icon name="briefcase" size={18} />
            </span>
            {copy.newCase}
          </Link>
          <Link href="/lawyer/clients/new" role="menuitem">
            <span>
              <Icon name="user" size={18} />
            </span>
            {copy.newClient}
          </Link>
        </div>
      ) : null}
      <button
        className={`quick-button ${open ? "is-open" : ""}`}
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-label={copy.quickActions}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <Icon name="plus" size={25} />
      </button>
    </div>
  );
}
