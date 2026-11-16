"use client";

import Link from "next/link";
import { useState } from "react";
import { Icon } from "@/components/Icon";
import type { ClientSummary } from "@/lib/api/lawyer";
import {
  dictionaries,
  format,
  numberFor,
  pick,
  type Language,
} from "@/lib/i18n";
import { initials } from "@/lib/initials";

export function ClientsList({
  language,
  clients,
}: {
  language: Language;
  clients: ClientSummary[];
}) {
  const copy = dictionaries[language].clients;
  const [query, setQuery] = useState("");
  const search = query.trim().toLowerCase();

  const filtered = clients.filter((client) =>
    [client.id, pick(client.name, language), client.phone, client.email]
      .join(" ")
      .toLowerCase()
      .includes(search),
  );

  return (
    <div className="panel matters-panel">
      <div className="table-tools">
        <label className="search-box">
          <Icon name="search" size={19} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={copy.search}
            aria-label={copy.search}
          />
        </label>
      </div>

      {filtered.length ? (
        <div className="client-list">
          {filtered.map((client) => (
            <Link
              className="client-row"
              key={client.id}
              href={`/lawyer/clients/${client.id}`}
            >
              <span className="avatar">{initials(client.name.en)}</span>
              <span className="client-identity">
                <b>{pick(client.name, language)}</b>
                <small>{client.id}</small>
              </span>
              <span className="client-contact">
                <span>{client.phone}</span>
                <small>{client.email}</small>
              </span>
              <span className="case-count">
                {format(copy.caseCount, {
                  count: numberFor(language, client.caseCount),
                })}
              </span>
              <Icon name="chevron" size={18} />
            </Link>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <Icon name="clients" />
          <b>{copy.empty}</b>
        </div>
      )}
    </div>
  );
}
