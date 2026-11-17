"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  setDocumentStatusAction,
  uploadDocumentAction,
} from "@/app/lawyer/actions";
import { HearingsTimeline } from "@/components/lawyer/HearingsTimeline";
import {
  DocumentList,
  HearingUpload,
  SummaryBadge,
  hearingDateLabel,
} from "@/components/lawyer/hearingParts";
import type { CaseDocument, Hearing } from "@/lib/api/lawyer";
import { MAX_DOCUMENT_BYTES, isAllowedDocument } from "@/lib/documents";
import {
  format,
  numberFor,
  pick,
  type Dictionary,
  type Language,
} from "@/lib/i18n";

type Tab = "hearings" | "documents";

export function MatterWorkspace({
  caseId,
  hearings,
  initialDocuments,
  language,
  copy,
  locked,
  error,
}: {
  caseId: string;
  hearings: Hearing[];
  initialDocuments: CaseDocument[];
  language: Language;
  copy: Dictionary["caseDetail"];
  locked: boolean;
  error: "hearing" | "note" | null;
}) {
  const [tab, setTab] = useState<Tab>("hearings");
  const [caseDocuments, setCaseDocuments] = useState(initialDocuments);
  const [uploadErrors, setUploadErrors] = useState<Record<string, string>>({});
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach(clearTimeout);
  }, []);

  function markReady(documentId: string) {
    setCaseDocuments((items) =>
      items.map((item) =>
        item.id === documentId ? { ...item, status: "ready" } : item,
      ),
    );
    void setDocumentStatusAction(caseId, documentId, "ready");
  }

  async function handleUpload(hearingId: string, files: File[]) {
    if (files.length === 0) return;

    const messages = new Set<string>();
    for (const file of files) {
      if (!isAllowedDocument(file.name, file.type)) {
        messages.add(copy.uploadTypeError);
      }
      if (file.size > MAX_DOCUMENT_BYTES) {
        messages.add(copy.uploadSizeError);
      }
    }

    const errors = [...messages];
    setUploadErrors((previous) => ({
      ...previous,
      [hearingId]: errors.join(" "),
    }));
    if (errors.length > 0) return;

    const pending: CaseDocument[] = files.map((file) => ({
      id: `temp-${crypto.randomUUID()}`,
      hearingId,
      name: file.name,
      size: file.size,
      mimeType: file.type,
      status: "uploading",
    }));
    setCaseDocuments((items) => [...items, ...pending]);

    await Promise.all(
      files.map(async (file, index) => {
        const saved = await uploadDocumentAction({
          caseId,
          hearingId,
          name: file.name,
          size: file.size,
          mimeType: file.type,
        });

        if (!saved) {
          setCaseDocuments((items) =>
            items.map((item) =>
              item.id === pending[index].id
                ? { ...item, status: "failed" }
                : item,
            ),
          );
          setUploadErrors((previous) => ({
            ...previous,
            [hearingId]: copy.uploadFailed,
          }));
          return;
        }

        setCaseDocuments((items) =>
          items.map((item) => (item.id === pending[index].id ? saved : item)),
        );
        timers.current.push(setTimeout(() => markReady(saved.id), 1400));
      }),
    );
  }

  function handleRetry(document: CaseDocument) {
    setCaseDocuments((items) =>
      items.map((item) =>
        item.id === document.id ? { ...item, status: "processing" } : item,
      ),
    );
    void setDocumentStatusAction(caseId, document.id, "processing");
    timers.current.push(setTimeout(() => markReady(document.id), 1400));
  }

  const tabClass = (active: boolean) =>
    `rounded-md px-3 py-1.5 text-[10px] font-bold transition-colors ${
      active
        ? "bg-[var(--color-deep)] text-white"
        : "text-[color:var(--color-muted)] hover:text-[color:var(--color-deep)]"
    }`;

  return (
    <div className="col-span-full">
      <div
        className="mb-3 inline-flex items-center gap-1 rounded-lg border border-[color:var(--color-border)] bg-white p-1"
        role="tablist"
      >
        <button
          type="button"
          role="tab"
          aria-selected={tab === "hearings"}
          className={tabClass(tab === "hearings")}
          onClick={() => setTab("hearings")}
        >
          {copy.tabs.hearings}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "documents"}
          className={tabClass(tab === "documents")}
          onClick={() => setTab("documents")}
        >
          {copy.tabs.documents}
        </button>
      </div>

      {tab === "hearings" ? (
        <HearingsTimeline
          caseId={caseId}
          hearings={hearings}
          documents={caseDocuments}
          uploadErrors={uploadErrors}
          language={language}
          copy={copy}
          locked={locked}
          error={error}
          onUpload={handleUpload}
          onRetry={handleRetry}
        />
      ) : (
        <div className="panel col-span-full">
          <div className="panel-head">
            <div>
              <h2>{copy.documentsTitle}</h2>
              <p>{copy.documentsSub}</p>
            </div>
            <span className="count-chip">
              {format(copy.documentsCount, {
                count: numberFor(language, caseDocuments.length),
              })}
            </span>
          </div>

          <p className="mt-3 rounded-md border border-dashed border-[color:var(--color-border)] bg-[#fbfaf6] px-3 py-2 text-[9px] leading-relaxed text-[color:var(--color-muted)]">
            {copy.documentsMock}
          </p>

          {hearings.length === 0 ? (
            <p className="mt-4 text-[10px] text-[color:var(--color-muted)]">
              {copy.noHearings}
            </p>
          ) : (
            <div className="mt-4 grid gap-4">
              {hearings.map((hearing) => (
                <section
                  key={hearing.id}
                  className="border-t border-[color:var(--color-border)] pt-4 first:border-0 first:pt-0"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <h3 className="text-[11px] font-bold text-[color:var(--color-ink)]">
                        {format(copy.hearing, {
                          number: numberFor(language, hearing.number),
                        })}
                      </h3>
                      <p className="mt-0.5 text-[9px] text-[color:var(--color-muted)]">
                        {hearingDateLabel(hearing.date, language)} ·{" "}
                        {pick(hearing.court, language)}
                      </p>
                    </div>
                    <SummaryBadge status={hearing.summaryStatus} copy={copy} />
                    <Link
                      className="text-[8px] font-bold text-[color:var(--color-deep)] underline underline-offset-2"
                      href={`/lawyer/matters/${caseId}/hearings/${hearing.id}/summary`}
                    >
                      {copy.viewSummary}
                    </Link>
                  </div>

                  <DocumentList
                    documents={caseDocuments.filter(
                      (document) => document.hearingId === hearing.id,
                    )}
                    language={language}
                    copy={copy}
                    onRetry={handleRetry}
                  />

                  {!locked ? (
                    <HearingUpload
                      hearingId={hearing.id}
                      copy={copy}
                      error={uploadErrors[hearing.id]}
                      onUpload={handleUpload}
                    />
                  ) : null}
                </section>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
