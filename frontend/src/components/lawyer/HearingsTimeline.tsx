"use client";

import Link from "next/link";
import { addHearingAction, addHearingNoteAction } from "@/app/lawyer/actions";
import { Icon } from "@/components/Icon";
import {
  DocumentList,
  HearingUpload,
  SummaryBadge,
  hearingDateLabel,
} from "@/components/lawyer/hearingParts";
import {
  HearingUpdateForm,
  ReassessmentCard,
} from "@/components/lawyer/hearingUpdate";
import type { CaseDocument, Hearing, Reassessment } from "@/lib/api/lawyerTypes";
import {
  format,
  numberFor,
  pick,
  type Dictionary,
  type Language,
} from "@/lib/i18n";

const inputClass =
  "w-full rounded-[9px] border border-[color:var(--color-border)] bg-[color:var(--color-surface)] px-3 text-[11px] text-[color:var(--color-text)] outline-none focus:border-[color:var(--color-green)]";

export function HearingsTimeline({
  caseId,
  hearings,
  documents,
  uploadErrors,
  language,
  copy,
  locked,
  error,
  onUpload,
  onRetry,
  reassessments,
  demo,
}: {
  caseId: string;
  hearings: Hearing[];
  documents: CaseDocument[];
  uploadErrors: Record<string, string>;
  language: Language;
  copy: Dictionary["caseDetail"];
  locked: boolean;
  error: "hearing" | "note" | null;
  onUpload: (hearingId: string, files: File[]) => void | Promise<void>;
  onRetry: (document: CaseDocument) => void;
  reassessments: Reassessment[];
  demo: boolean;
}) {
  return (
    <div className="panel col-span-full">
      <div className="panel-head">
        <div>
          <h2>{copy.hearingsTitle}</h2>
          <p>{copy.hearingsSub}</p>
        </div>
        <span className="count-chip">
          {format(copy.hearingsCount, {
            count: numberFor(language, hearings.length),
          })}
        </span>
      </div>

      {demo ? (
        <p className="mt-3 rounded-md border border-dashed border-[color:var(--color-border)] bg-[color:var(--color-surface)] px-3 py-2 text-[9px] leading-relaxed text-[color:var(--color-muted)]">
          {copy.hearingMock}
        </p>
      ) : null}

      {error ? (
        <p className="form-error" role="alert">
          {error === "hearing" ? copy.hearingError : copy.noteError}
        </p>
      ) : null}

      {hearings.length === 0 ? (
        <p className="mt-4 text-[10px] text-[color:var(--color-muted)]">
          {copy.noHearings}
        </p>
      ) : (
        <ol className="mt-5">
          {hearings.map((hearing, index) => {
            const current = index === hearings.length - 1;
            const currentNote = hearing.notes[hearing.notes.length - 1];
            const edited = hearing.notes.length > 1;
            const reassessment = reassessments.find(
              (item) => item.hearingId === hearing.id,
            );

            return (
              <li
                key={hearing.id}
                className="relative border-l border-[color:var(--color-border)] pb-6 pl-6 last:border-transparent last:pb-1"
              >
                <span
                  aria-hidden="true"
                  className={`absolute -left-[5px] top-1 h-2.5 w-2.5 rounded-full border-2 border-white ${
                    current
                      ? "bg-[var(--color-green)] shadow-[0_0_0_1px_var(--color-green),0_0_0_5px_#eaf6ef]"
                      : "bg-[#b8c0c4] shadow-[0_0_0_1px_#b8c0c4]"
                  }`}
                />
                <div className="flex flex-col">
                  <small className="text-[8px] font-bold text-[color:var(--color-green)]">
                    {hearingDateLabel(hearing.date, language)}
                  </small>
                  <div className="mt-1.5 flex flex-wrap items-center gap-2">
                    <b className="text-[11px] text-[color:var(--color-ink)]">
                      {format(copy.hearing, {
                        number: numberFor(language, hearing.number),
                      })}
                    </b>
                    <SummaryBadge status={hearing.summaryStatus} copy={copy} />
                    <Link
                      className="text-[8px] font-bold text-[color:var(--color-deep)] underline underline-offset-2"
                      href={`/lawyer/matters/${caseId}/hearings/${hearing.id}/summary`}
                    >
                      {copy.viewSummary}
                    </Link>
                  </div>
                  <span className="mt-0.5 text-[9px] text-[color:var(--color-muted)]">
                    {pick(hearing.court, language)}
                  </span>
                  <p className="mt-1.5 break-words text-[10px] leading-relaxed text-[color:var(--color-muted)]">
                    {currentNote.text}
                  </p>

                  <div className="mt-2">
                    {edited ? (
                      <span className="mr-2 inline-flex rounded-full bg-[#eaf6ef] px-2 py-0.5 text-[8px] font-bold text-[color:var(--color-deep)]">
                        {copy.edited}
                      </span>
                    ) : null}

                    <details className="mt-1">
                      <summary className="cursor-pointer list-none text-[8px] font-bold text-[color:var(--color-deep)]">
                        {copy.noteHistory} ·{" "}
                        {format(copy.versionCount, {
                          count: numberFor(language, hearing.notes.length),
                        })}
                      </summary>
                      <ol className="mt-2 grid gap-2">
                        {hearing.notes.map((version, versionIndex) => (
                          <li
                            key={version.id}
                            className="rounded-md bg-[color:var(--color-surface)] px-2.5 py-2"
                          >
                            <small className="text-[8px] font-bold text-[color:var(--color-deep)]">
                              {format(copy.versionNumber, {
                                number: numberFor(language, versionIndex + 1),
                              })}
                              {versionIndex === hearing.notes.length - 1
                                ? ` · ${copy.currentVersion}`
                                : ""}
                            </small>
                            <p className="mt-1 break-words text-[10px] leading-relaxed text-[color:var(--color-text)]">
                              {version.text}
                            </p>
                          </li>
                        ))}
                      </ol>

                      {locked ? (
                        <p className="mt-3 text-[9px] text-[color:var(--color-muted)]">
                          {copy.hearingsLocked}
                        </p>
                      ) : !demo ? (
                        <HearingUpdateForm
                          caseId={caseId}
                          hearingId={hearing.id}
                          copy={copy.ai}
                        />
                      ) : (
                        <form action={addHearingNoteAction} className="mt-3">
                          <input type="hidden" name="caseId" value={caseId} />
                          <input
                            type="hidden"
                            name="hearingId"
                            value={hearing.id}
                          />
                          <label
                            className="block"
                            htmlFor={`note-${hearing.id}`}
                          >
                            <span className="field-label">{copy.addNote}</span>
                            <textarea
                              id={`note-${hearing.id}`}
                              name="note"
                              required
                              rows={2}
                              placeholder={copy.notePlaceholder}
                              className={`${inputClass} min-h-[70px] py-2`}
                            />
                          </label>
                          <button
                            className="primary-button fit mt-2"
                            type="submit"
                          >
                            {copy.saveNote}
                          </button>
                        </form>
                      )}
                    </details>
                    {reassessment ? (
                      <ReassessmentCard
                        reassessment={reassessment}
                        language={language}
                        copy={copy.ai}
                      />
                    ) : null}
                  </div>

                  <div className="mt-3 border-t border-[color:var(--color-border)] pt-3">
                    <DocumentList
                      documents={documents.filter(
                        (document) => document.hearingId === hearing.id,
                      )}
                      language={language}
                      copy={copy}
                      onRetry={onRetry}
                      share={locked || demo ? undefined : { caseId, tab: "hearings" }}
                    />
                    {!locked ? (
                      <HearingUpload
                        hearingId={hearing.id}
                        copy={copy}
                        error={uploadErrors[hearing.id]}
                        onUpload={onUpload}
                      />
                    ) : null}
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      )}

      {locked ? (
        <p className="mt-5 border-t border-[color:var(--color-border)] pt-4 text-[10px] text-[color:var(--color-muted)]">
          {copy.hearingsLocked}
        </p>
      ) : (
        <form
          action={addHearingAction}
          className="mt-5 border-t border-[color:var(--color-border)] pt-4"
        >
          <input type="hidden" name="caseId" value={caseId} />
          <h3 className="m-0 flex items-center gap-2 text-[12px] font-bold text-[color:var(--color-ink)]">
            <Icon name="plus" size={15} />
            {copy.addHearing}
          </h3>
          <div className="mt-3 grid gap-3 sm:grid-cols-[200px_1fr]">
            <label className="block" htmlFor="hearing-date">
              <span className="field-label">{copy.hearingDate}</span>
              <input
                id="hearing-date"
                name="date"
                type="date"
                required
                className={`${inputClass} h-11`}
              />
            </label>
            <label className="block" htmlFor="hearing-note">
              <span className="field-label">{copy.hearingNotes}</span>
              <textarea
                id="hearing-note"
                name="note"
                required
                rows={3}
                placeholder={copy.hearingNotesPlaceholder}
                className={`${inputClass} min-h-[76px] py-2`}
              />
            </label>
          </div>
          <p className="mt-2 text-[9px] leading-relaxed text-[color:var(--color-muted)]">
            {copy.hearingDateHint}
          </p>
          <div className="mt-3 flex justify-end">
            <button className="primary-button fit" type="submit">
              {copy.saveHearing}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
