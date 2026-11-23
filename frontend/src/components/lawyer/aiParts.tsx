import type { ReactNode } from "react";
import type { Citation, Strength, Verification } from "@/lib/api/lawyerTypes";
import type { Dictionary } from "@/lib/i18n";

export type AiCopy = Dictionary["caseDetail"]["ai"];

export const inputClass =
  "w-full rounded-[9px] border border-[color:var(--color-border)] bg-[color:var(--color-surface)] px-3 text-[11px] text-[color:var(--color-text)] outline-none focus:border-[color:var(--color-green)]";

const strengthTone: Record<Strength, string> = {
  strong: "bg-[#eaf6ef] text-[var(--color-deep)]",
  moderate: "bg-[color:var(--color-pale)] text-[#26617f]",
  weak: "bg-[#f5efe1] text-[#806b43]",
  insufficient: "bg-[color:var(--color-surface)] text-[color:var(--color-muted)]",
};

export function Pill({ tone, children }: { tone: string; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[8px] font-bold ${tone}`}
    >
      {children}
    </span>
  );
}

export function StrengthBadge({ strength, copy }: { strength: Strength; copy: AiCopy }) {
  return <Pill tone={strengthTone[strength]}>{copy.strength[strength]}</Pill>;
}

export function VerificationBadge({
  verification,
  copy,
}: {
  verification: Verification;
  copy: AiCopy;
}) {
  return verification === "verified" ? (
    <Pill tone="bg-[#eaf6ef] text-[var(--color-deep)]">{copy.verified}</Pill>
  ) : (
    <Pill tone="bg-[#eef0f2] text-[#3c4347]">{copy.unverified}</Pill>
  );
}

/** "Act, s. 138" with the verified quote; links to the official source when known. */
export function CitationLine({ citation, copy }: { citation: Citation; copy: AiCopy }) {
  const label = [citation.act, citation.section && `s. ${citation.section}`]
    .filter(Boolean)
    .join(", ");
  return (
    <div className="mt-1.5 rounded-md bg-[color:var(--color-surface)] px-2.5 py-2">
      <div className="flex flex-wrap items-center gap-2">
        {citation.url ? (
          <a
            className="text-[9px] font-bold text-[color:var(--color-deep)] underline underline-offset-2"
            href={citation.url}
            target="_blank"
            rel="noopener noreferrer"
          >
            {label}
          </a>
        ) : (
          <b className="text-[9px] text-[color:var(--color-ink)]">{label}</b>
        )}
        <VerificationBadge verification={citation.verification} copy={copy} />
      </div>
      {citation.quote ? (
        <p className="mt-1 break-words text-[9px] italic leading-relaxed text-[color:var(--color-muted)]">
          “{citation.quote}”
        </p>
      ) : null}
    </div>
  );
}

export function TextList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="mt-2">
      <span className="field-label">{title}</span>
      <ul className="mt-1 list-disc pl-4 text-[10px] leading-relaxed text-[color:var(--color-text)]">
        {items.map((item, index) => (
          <li key={`${index}-${item}`} className="break-words">
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Draft notice plus where the output came from: "ai (groq)" or the labelled mock. */
export function DraftNotice({ copy, aiMock, provider }: { copy: AiCopy; aiMock: boolean; provider?: string }) {
  return (
    <p className="mt-3 rounded-md border border-dashed border-[color:var(--color-border)] bg-[color:var(--color-surface)] px-3 py-2 text-[9px] leading-relaxed text-[color:var(--color-muted)]">
      {copy.draftNotice}
      {aiMock ? (
        <b className="ml-1 text-[#806b43]">{copy.mockOrigin}</b>
      ) : provider ? (
        <b className="ml-1 text-[color:var(--color-deep)]">{copy.aiOrigin.replace("{provider}", provider)}</b>
      ) : null}
    </p>
  );
}
