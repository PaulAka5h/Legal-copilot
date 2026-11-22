import {
  addFactAction,
  confirmFactAction,
  editFactAction,
  extractFactsAction,
  rejectFactAction,
} from "@/app/lawyer/actions";
import { Icon } from "@/components/Icon";
import { Pill, inputClass, type AiCopy } from "@/components/lawyer/aiParts";
import type { CaseFact, FactCategory } from "@/lib/api/lawyerTypes";
import { format, numberFor, type Language } from "@/lib/i18n";

const CATEGORIES: FactCategory[] = [
  "act_or_omission",
  "party",
  "date",
  "place",
  "document",
  "relief_sought",
  "other",
];

const reviewTone: Record<CaseFact["review"], string> = {
  draft: "bg-[#f5efe1] text-[#806b43]",
  lawyer_reviewed: "bg-[var(--brand-100)] text-[var(--brand-800)]",
  lawyer_rejected: "bg-[#f8e9e5] text-[#8a2e1e]",
};

/** Prefilled edit of a fact whose quote was not found: opens with one click. */
function EditFactForm({
  caseId,
  fact,
  language,
  copy,
}: {
  caseId: string;
  fact: CaseFact;
  language: Language;
  copy: AiCopy;
}) {
  const source = fact.sources.find((item) => item.documentId && item.page !== null);
  if (!source?.documentId || source.page === null) return null;
  return (
    <details className="mt-2">
      <summary className="outline-button small inline-flex cursor-pointer list-none">
        <Icon name="document" size={14} />
        {copy.editFact}
      </summary>
      <form action={editFactAction} className="mt-3 grid gap-3">
        <input type="hidden" name="caseId" value={caseId} />
        <input type="hidden" name="factId" value={fact.id} />
        <input type="hidden" name="documentId" value={source.documentId} />
        <input type="hidden" name="page" value={source.page} />
        <p className="m-0 text-[9px] leading-relaxed text-[color:var(--color-muted)]">{copy.editFactHint}</p>
        <label className="block" htmlFor={`edit-statement-${fact.id}`}>
          <span className="field-label">{copy.factStatement}</span>
          <textarea
            id={`edit-statement-${fact.id}`}
            name="statement"
            required
            maxLength={4000}
            rows={2}
            defaultValue={fact.statement}
            className={`${inputClass} min-h-[60px] py-2`}
          />
        </label>
        <label className="block" htmlFor={`edit-quote-${fact.id}`}>
          <span className="field-label">
            {format(copy.editFactQuote, { page: numberFor(language, source.page) })}
          </span>
          <textarea
            id={`edit-quote-${fact.id}`}
            name="quote"
            required
            maxLength={2000}
            rows={3}
            defaultValue={source.quote ?? ""}
            className={`${inputClass} min-h-[70px] py-2`}
          />
        </label>
        <div className="flex justify-end">
          <button className="primary-button fit" type="submit">
            {copy.saveEditedFact}
          </button>
        </div>
      </form>
    </details>
  );
}

function FactItem({
  caseId,
  fact,
  language,
  copy,
  locked,
  quoteError,
}: {
  caseId: string;
  fact: CaseFact;
  language: Language;
  copy: AiCopy;
  locked: boolean;
  quoteError: boolean;
}) {
  const reviewable = !locked && fact.review === "draft";
  const quoteMissing =
    fact.statementType === "document_says" &&
    fact.sources.some((source) => source.page !== null && source.verification !== "verified");
  return (
    <li
      id={`fact-${fact.id}`}
      className={`border-t border-[color:var(--color-border)] py-3 first:border-0 ${
        quoteError ? "scroll-mt-24 rounded-md bg-[#fdf3f0] px-2" : ""
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone={reviewTone[fact.review]}>{copy.review[fact.review]}</Pill>
        <Pill tone="bg-[color:var(--color-surface)] text-[color:var(--color-muted)]">
          {copy.statementType[fact.statementType]}
        </Pill>
        <Pill tone="bg-[color:var(--color-surface)] text-[color:var(--color-muted)]">
          {copy.categories[fact.category]}
        </Pill>
        {fact.usableInAnalysis ? (
          <Pill tone="bg-[var(--brand-100)] text-[var(--brand-800)]">{copy.usable}</Pill>
        ) : null}
        {fact.aiMock ? (
          <Pill tone="bg-[#f5efe1] text-[#806b43]">{copy.mockOrigin}</Pill>
        ) : null}
      </div>
      <p className="mt-1.5 break-words text-[10px] leading-relaxed text-[color:var(--color-text)]">
        {fact.statement}
      </p>
      {fact.sources.map((source, index) => (
        <p
          key={index}
          className="mt-1 break-words text-[9px] italic leading-relaxed text-[color:var(--color-muted)]"
        >
          {source.page !== null
            ? `${format(copy.page, { page: numberFor(language, source.page) })} · `
            : ""}
          {source.quote ? `“${source.quote}” · ` : ""}
          {source.verification === "verified" ? copy.verified : copy.unverified}
        </p>
      ))}
      {reviewable && (quoteMissing || quoteError) ? (
        <>
          <p className="mt-1.5 text-[9px] font-semibold text-[#8a2e1e]" role={quoteError ? "alert" : undefined}>
            {quoteError ? copy.quoteNotFound : copy.quoteUnverified}
          </p>
          <EditFactForm caseId={caseId} fact={fact} language={language} copy={copy} />
        </>
      ) : null}
      {reviewable ? (
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <form action={confirmFactAction}>
            <input type="hidden" name="caseId" value={caseId} />
            <input type="hidden" name="factId" value={fact.id} />
            <button className="primary-button fit" type="submit">
              {copy.confirm}
            </button>
          </form>
          <form action={rejectFactAction} className="flex flex-wrap items-end gap-2">
            <input type="hidden" name="caseId" value={caseId} />
            <input type="hidden" name="factId" value={fact.id} />
            <label className="block" htmlFor={`reject-${fact.id}`}>
              <span className="field-label">{copy.rejectReason}</span>
              <input
                id={`reject-${fact.id}`}
                name="note"
                maxLength={1000}
                className={`${inputClass} h-9`}
              />
            </label>
            <button className="outline-button small" type="submit">
              {copy.reject}
            </button>
          </form>
        </div>
      ) : null}
    </li>
  );
}

export function FactsPanel({
  caseId,
  facts,
  language,
  copy,
  locked,
  quoteErrorFactId = null,
}: {
  caseId: string;
  facts: CaseFact[];
  language: Language;
  copy: AiCopy;
  locked: boolean;
  quoteErrorFactId?: string | null;
}) {
  const visible = facts.filter((fact) => fact.review !== "lawyer_rejected");
  return (
    <div className="panel col-span-full">
      <div className="panel-head">
        <div>
          <h2>{copy.factsTitle}</h2>
          <p>{copy.factsSub}</p>
        </div>
        <span className="count-chip">{numberFor(language, visible.length)}</span>
      </div>

      {visible.length === 0 ? (
        <p className="mt-4 text-[10px] text-[color:var(--color-muted)]">{copy.factsEmpty}</p>
      ) : (
        <ul className="mt-3">
          {visible.map((fact) => (
            <FactItem
              key={fact.id}
              caseId={caseId}
              fact={fact}
              language={language}
              copy={copy}
              locked={locked}
              quoteError={fact.id === quoteErrorFactId}
            />
          ))}
        </ul>
      )}

      {!locked ? (
        <div className="mt-5 grid gap-4 border-t border-[color:var(--color-border)] pt-4">
          <form action={addFactAction}>
            <input type="hidden" name="caseId" value={caseId} />
            <h3 className="m-0 flex items-center gap-2 text-[12px] font-bold text-[color:var(--color-ink)]">
              <Icon name="plus" size={15} />
              {copy.addFact}
            </h3>
            <div className="mt-3 grid gap-3 sm:grid-cols-[200px_1fr]">
              <label className="block" htmlFor="fact-category">
                <span className="field-label">{copy.factCategory}</span>
                <select
                  id="fact-category"
                  name="category"
                  defaultValue="act_or_omission"
                  className={`${inputClass} h-11`}
                >
                  {CATEGORIES.map((category) => (
                    <option key={category} value={category}>
                      {copy.categories[category]}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block" htmlFor="fact-statement">
                <span className="field-label">{copy.factStatement}</span>
                <textarea
                  id="fact-statement"
                  name="statement"
                  required
                  maxLength={4000}
                  rows={2}
                  placeholder={copy.factPlaceholder}
                  className={`${inputClass} min-h-[70px] py-2`}
                />
              </label>
            </div>
            <div className="mt-3 flex justify-end">
              <button className="primary-button fit" type="submit">
                {copy.saveFact}
              </button>
            </div>
          </form>
          <form action={extractFactsAction} className="flex justify-end">
            <input type="hidden" name="caseId" value={caseId} />
            <button className="outline-button small" type="submit">
              {copy.extract}
            </button>
          </form>
        </div>
      ) : null}
    </div>
  );
}
