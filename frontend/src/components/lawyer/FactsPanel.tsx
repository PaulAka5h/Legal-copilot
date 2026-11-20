import {
  addFactAction,
  confirmFactAction,
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
  lawyer_reviewed: "bg-[#eaf6ef] text-[var(--color-deep)]",
  lawyer_rejected: "bg-[#f8e9e5] text-[#8a2e1e]",
};

function FactItem({
  caseId,
  fact,
  language,
  copy,
  locked,
}: {
  caseId: string;
  fact: CaseFact;
  language: Language;
  copy: AiCopy;
  locked: boolean;
}) {
  const reviewable = !locked && fact.review === "draft";
  return (
    <li className="border-t border-[color:var(--color-border)] py-3 first:border-0">
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone={reviewTone[fact.review]}>{copy.review[fact.review]}</Pill>
        <Pill tone="bg-[color:var(--color-surface)] text-[color:var(--color-muted)]">
          {copy.statementType[fact.statementType]}
        </Pill>
        <Pill tone="bg-[color:var(--color-surface)] text-[color:var(--color-muted)]">
          {copy.categories[fact.category]}
        </Pill>
        {fact.usableInAnalysis ? (
          <Pill tone="bg-[#eaf6ef] text-[var(--color-deep)]">{copy.usable}</Pill>
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
}: {
  caseId: string;
  facts: CaseFact[];
  language: Language;
  copy: AiCopy;
  locked: boolean;
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
