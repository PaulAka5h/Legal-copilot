"use client";

import { useRef, useState } from "react";
import { toggleDocumentShareAction } from "@/app/lawyer/actions";
import { Icon } from "@/components/Icon";
import type {
  CaseDocument,
  DocumentStatus,
  SummaryStatus,
} from "@/lib/api/lawyer";
import {
  format,
  numberFor,
  type Dictionary,
  type Language,
} from "@/lib/i18n";

export function hearingDateLabel(date: string, language: Language) {
  const label = new Intl.DateTimeFormat(language === "bn" ? "bn-BD" : "en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${date}T00:00:00Z`));

  return language === "en" ? label.toUpperCase() : label;
}

function fileSize(
  size: number,
  language: Language,
  copy: Dictionary["caseDetail"],
) {
  const kilobytes = size / 1024;
  const value =
    kilobytes < 1024
      ? Math.round(kilobytes)
      : (kilobytes / 1024).toFixed(1);
  const template = kilobytes < 1024 ? copy.sizeKb : copy.sizeMb;

  return format(template, { value: numberFor(language, value) });
}

const statusTone: Record<DocumentStatus, string> = {
  uploading: "text-[#806b43]",
  processing: "text-[#26617f]",
  ready: "text-[var(--color-deep)]",
  failed: "text-[#8a2e1e]",
};

const summaryTone: Record<SummaryStatus, string> = {
  none: "bg-[color:var(--color-surface)] text-[color:var(--color-muted)]",
  processing: "bg-[#f5efe1] text-[#806b43]",
  draft_ready: "bg-[color:var(--color-pale)] text-[#26617f]",
  approved: "bg-[#eaf6ef] text-[var(--color-deep)]",
};

export function SummaryBadge({
  status,
  copy,
}: {
  status: SummaryStatus;
  copy: Dictionary["caseDetail"];
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[8px] font-bold ${summaryTone[status]}`}
    >
      {copy.summaryLabel}: {copy.summary[status]}
    </span>
  );
}

export function DocumentList({
  documents,
  language,
  copy,
  onRetry,
  share,
}: {
  documents: CaseDocument[];
  language: Language;
  copy: Dictionary["caseDetail"];
  onRetry: (document: CaseDocument) => void;
  /** Share-with-client toggle; omitted for closed cases and demo data. */
  share?: { caseId: string; tab: "hearings" | "documents" };
}) {
  if (documents.length === 0) {
    return (
      <p className="mt-2 text-[9px] text-[color:var(--color-muted)]">
        {copy.documentsEmpty}
      </p>
    );
  }

  return (
    <ul className="mt-2 grid gap-1.5">
      {documents.map((document) => (
        <li
          key={document.id}
          className="flex items-center justify-between gap-2 rounded-md bg-[color:var(--color-surface)] px-2.5 py-1.5"
        >
          <div className="min-w-0">
            <p className="truncate text-[10px] font-semibold text-[color:var(--color-ink)]">
              {document.name}
            </p>
            <small className="text-[8px] text-[color:var(--color-muted)]">
              {fileSize(document.size, language, copy)} ·{" "}
              <span className={statusTone[document.status]}>
                {copy.documentStatus[document.status]}
              </span>
            </small>
          </div>
          {document.status === "failed" ? (
            <button
              type="button"
              className="shrink-0 text-[8px] font-bold text-[#8a2e1e] underline"
              onClick={() => onRetry(document)}
            >
              {copy.retry}
            </button>
          ) : share && document.status === "ready" ? (
            <form action={toggleDocumentShareAction} className="flex shrink-0 items-center gap-1.5">
              <input type="hidden" name="caseId" value={share.caseId} />
              <input type="hidden" name="documentId" value={document.id} />
              <input type="hidden" name="tab" value={share.tab} />
              <input type="hidden" name="share" value={document.sharedWithClient ? "0" : "1"} />
              {document.sharedWithClient ? (
                <span className="rounded-full bg-[#eaf6ef] px-2 py-0.5 text-[8px] font-bold text-[var(--color-deep)]">
                  {copy.sharedWithClient}
                </span>
              ) : null}
              <button
                type="submit"
                role="switch"
                aria-checked={Boolean(document.sharedWithClient)}
                className="text-[8px] font-bold text-[color:var(--color-deep)] underline underline-offset-2"
              >
                {document.sharedWithClient ? copy.stopSharing : copy.shareWithClient}
              </button>
            </form>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

export function HearingUpload({
  hearingId,
  copy,
  error,
  onUpload,
}: {
  hearingId: string;
  copy: Dictionary["caseDetail"];
  error?: string;
  onUpload: (hearingId: string, files: File[]) => void | Promise<void>;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const inputId = `upload-${hearingId}`;

  return (
    <div
      className={`mt-3 rounded-lg border border-dashed px-3 py-2.5 transition-colors ${
        dragging
          ? "border-[var(--color-green)] bg-[#eaf6ef]"
          : "border-[color:var(--color-border)] bg-[color:var(--color-surface)]"
      }`}
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        void onUpload(hearingId, Array.from(event.dataTransfer.files));
      }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          className="outline-button small"
          onClick={() => inputRef.current?.click()}
        >
          <Icon name="document" size={15} />
          {copy.uploadDocuments}
        </button>
        <label
          className="cursor-pointer text-[9px] leading-relaxed text-[color:var(--color-muted)]"
          htmlFor={inputId}
        >
          {copy.uploadHint}
        </label>
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          multiple
          accept="application/pdf,image/*"
          className="hidden"
          onChange={(event) => {
            const files = Array.from(event.target.files ?? []);
            event.target.value = "";
            void onUpload(hearingId, files);
          }}
        />
      </div>
      {error ? (
        <p
          className="mt-2 text-[9px] font-semibold text-[#8a2e1e]"
          role="alert"
        >
          {error}
        </p>
      ) : null}
    </div>
  );
}
