"use client";

import Link from "next/link";
import { useState } from "react";
import { Icon } from "@/components/Icon";
import type { Matter, MatterStatus } from "@/lib/api/lawyer";
import {
  dictionaries,
  format,
  numberFor,
  pick,
  type Language,
} from "@/lib/i18n";

type Filter = "all" | MatterStatus;

const filters: Filter[] = ["all", "active", "on_hold", "closed"];

export function MattersTable({
  language,
  matters,
}: {
  language: Language;
  matters: Matter[];
}) {
  const copy = dictionaries[language].matters;
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");

  const counts = {
    all: matters.length,
    active: matters.filter((matter) => matter.status === "active").length,
    on_hold: matters.filter((matter) => matter.status === "on_hold").length,
    closed: matters.filter((matter) => matter.status === "closed").length,
  };

  const search = query.trim().toLowerCase();
  const filtered = matters.filter((matter) => {
    if (filter !== "all" && matter.status !== filter) return false;
    if (!search) return true;

    return [
      matter.id,
      pick(matter.title, language),
      pick(matter.clientName, language),
      pick(matter.court, language),
    ]
      .join(" ")
      .toLowerCase()
      .includes(search);
  });

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
        <div className="filter-pills">
          {filters.map((key) => (
            <button
              key={key}
              type="button"
              className={filter === key ? "active" : ""}
              aria-pressed={filter === key}
              onClick={() => setFilter(key)}
            >
              {copy.filters[key]} <span>{numberFor(language, counts[key])}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="matters-table">
        <div className="table-row table-header">
          <span>{copy.columns.matter}</span>
          <span>{copy.columns.client}</span>
          <span>{copy.columns.court}</span>
          <span>{copy.columns.hearing}</span>
          <span>{copy.columns.status}</span>
        </div>

        {filtered.map((matter) => (
          <Link
            className="table-row"
            href={`/lawyer/matters/${matter.id}`}
            key={matter.id}
          >
            <span className="matter-cell">
              <small>{matter.id}</small>
              <b>
                {pick(matter.title, language)}
                {matter.archived ? <span className="archived-chip">{copy.archived}</span> : null}
              </b>
            </span>
            <span data-label={copy.columns.client}>
              {pick(matter.clientName, language)}
            </span>
            <span data-label={copy.columns.court}>
              {pick(matter.court, language)}
            </span>
            <span data-label={copy.columns.hearing}>
              <b className="hearing-number">
                #{numberFor(language, matter.hearingNumber)}
              </b>
            </span>
            <span data-label={copy.columns.status}>
              <em
                className={`status ${matter.status === "closed" ? "status-closed" : ""}`}
              >
                <span /> {copy.status[matter.status]}
              </em>
            </span>
          </Link>
        ))}

        {!filtered.length ? (
          <div className="empty-state">
            <Icon name="search" />
            <b>{copy.empty}</b>
          </div>
        ) : null}
      </div>

      <div className="table-footer">
        <span>
          {format(copy.showing, {
            count: numberFor(language, filtered.length),
            total: numberFor(language, matters.length),
          })}
        </span>
      </div>
    </div>
  );
}
