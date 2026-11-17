"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import type { SharedDocument } from "@/lib/api/client";
import { pick, type Language } from "@/lib/i18n";

export function ClientDocuments({
  documents,
  language,
  download,
  notice,
}: {
  documents: SharedDocument[];
  language: Language;
  download: string;
  notice: string;
}) {
  const [toast, setToast] = useState("");

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 2600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  return (
    <>
      <div className="document-list">
        {documents.map((document) => (
          <div className="document-row" key={document.id}>
            <span className="pdf-icon">{document.format}</span>
            <span>
              <b>{pick(document.name, language)}</b>
              <small>
                {pick(document.size, language)} · {pick(document.sharedOn, language)}
              </small>
            </span>
            <button
              type="button"
              onClick={() => setToast(notice)}
              aria-label={`${download} ${pick(document.name, language)}`}
            >
              <Icon name="download" size={18} />
              <span>{download}</span>
            </button>
          </div>
        ))}
      </div>
      {toast ? (
        <div className="toast" role="status">
          <Icon name="check" size={18} /> {toast}
        </div>
      ) : null}
    </>
  );
}
