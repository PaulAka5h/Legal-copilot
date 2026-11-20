import { submitHearingUpdateAction } from "@/app/lawyer/actions";
import { Pill, TextList, inputClass, type AiCopy } from "@/components/lawyer/aiParts";
import { hearingDateLabel } from "@/components/lawyer/hearingParts";
import type { Reassessment } from "@/lib/api/lawyerTypes";
import { format, type Language } from "@/lib/i18n";

/** Order text, notes and a next date that counts only when the lawyer confirms it (Rule 5). */
export function HearingUpdateForm({
  caseId,
  hearingId,
  copy,
}: {
  caseId: string;
  hearingId: string;
  copy: AiCopy;
}) {
  return (
    <form action={submitHearingUpdateAction} className="mt-3">
      <input type="hidden" name="caseId" value={caseId} />
      <input type="hidden" name="hearingId" value={hearingId} />
      <span className="field-label">{copy.updateTitle}</span>
      <div className="mt-2 grid gap-3">
        <label className="block" htmlFor={`order-${hearingId}`}>
          <span className="field-label">{copy.orderText}</span>
          <textarea
            id={`order-${hearingId}`}
            name="orderText"
            required
            maxLength={8000}
            rows={2}
            placeholder={copy.orderPlaceholder}
            className={`${inputClass} min-h-[70px] py-2`}
          />
        </label>
        <label className="block" htmlFor={`outcome-${hearingId}`}>
          <span className="field-label">{copy.outcomeNotes}</span>
          <textarea
            id={`outcome-${hearingId}`}
            name="notes"
            maxLength={8000}
            rows={2}
            placeholder={copy.outcomePlaceholder}
            className={`${inputClass} min-h-[60px] py-2`}
          />
        </label>
        <div className="grid gap-3 sm:grid-cols-[200px_1fr] sm:items-end">
          <label className="block" htmlFor={`next-${hearingId}`}>
            <span className="field-label">{copy.nextDate}</span>
            <input
              id={`next-${hearingId}`}
              name="nextHearingDate"
              type="date"
              className={`${inputClass} h-11`}
            />
          </label>
          <label className="flex items-center gap-2 text-[10px] text-[color:var(--color-text)]">
            <input type="checkbox" name="nextHearingConfirmed" />
            {copy.confirmNext}
          </label>
        </div>
      </div>
      <p className="mt-2 text-[9px] leading-relaxed text-[color:var(--color-muted)]">{copy.nextDateHint}</p>
      <div className="mt-3 flex justify-end">
        <button className="primary-button fit" type="submit">
          {copy.saveUpdate}
        </button>
      </div>
    </form>
  );
}

export function ReassessmentCard({
  reassessment,
  language,
  copy,
}: {
  reassessment: Reassessment;
  language: Language;
  copy: AiCopy;
}) {
  const changes = reassessment.changes.map(
    (change) =>
      `${change.claim}: ${change.before ? copy.strength[change.before] : "—"} → ${
        change.after ? copy.strength[change.after] : "—"
      }`,
  );
  return (
    <div className="mt-3 rounded-md border border-[color:var(--color-border)] px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <b className="text-[10px] text-[color:var(--color-ink)]">{copy.reassessTitle}</b>
        {reassessment.treeVersion !== null ? (
          <Pill tone="bg-[color:var(--color-surface)] text-[color:var(--color-muted)]">
            {copy.strategyTitle} · {format(copy.version, { number: reassessment.treeVersion })}
          </Pill>
        ) : null}
        {reassessment.clientUpdateStatus ? (
          <Pill tone="bg-[color:var(--color-pale)] text-[#26617f]">
            {format(copy.clientUpdate, {
              status: copy.clientStatus[reassessment.clientUpdateStatus],
            })}
          </Pill>
        ) : null}
      </div>
      {reassessment.suggestedNextDate ? (
        <p className="mt-1.5 text-[9px] font-semibold text-[#806b43]">
          {format(copy.suggestedDate, {
            date: hearingDateLabel(reassessment.suggestedNextDate, language),
          })}
        </p>
      ) : null}
      <TextList title={copy.changes} items={changes} />
      <TextList title={copy.closedOptions} items={reassessment.closedOptions} />
      <TextList title={copy.newOptions} items={reassessment.newOptions} />
      <TextList title={copy.tasks} items={reassessment.tasks} />
    </div>
  );
}
