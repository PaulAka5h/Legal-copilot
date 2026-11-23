import { runAnalysisAction, runStrategyAction } from "@/app/lawyer/actions";
import {
  CitationLine,
  DraftNotice,
  Pill,
  StrengthBadge,
  TextList,
  VerificationBadge,
  type AiCopy,
} from "@/components/lawyer/aiParts";
import type {
  CaseAnalysis,
  Finding,
  StrategyMove,
  StrategyTree,
} from "@/lib/api/lawyerTypes";
import { format, numberFor, type Language } from "@/lib/i18n";

const elementTone = {
  met: "bg-[#eaf6ef] text-[var(--color-deep)]",
  missing: "bg-[#eef0f2] text-[#3c4347]",
  disputed: "bg-[#f5efe1] text-[#806b43]",
} as const;

function RunButton({
  action,
  caseId,
  label,
  disabled,
}: {
  action: (formData: FormData) => Promise<void>;
  caseId: string;
  label: string;
  disabled: boolean;
}) {
  return (
    <form action={action}>
      <input type="hidden" name="caseId" value={caseId} />
      <button className="primary-button fit" type="submit" disabled={disabled}>
        {label}
      </button>
    </form>
  );
}

function FindingCard({ finding, copy }: { finding: Finding; copy: AiCopy }) {
  return (
    <li className="border-t border-[color:var(--color-border)] py-3 first:border-0">
      <div className="flex flex-wrap items-center gap-2">
        <b className="text-[11px] text-[color:var(--color-ink)]">{finding.claim}</b>
        <StrengthBadge strength={finding.strength} copy={copy} />
        <VerificationBadge verification={finding.verification} copy={copy} />
      </div>
      <CitationLine citation={finding.citation} copy={copy} />
      {finding.elements.length > 0 ? (
        <div className="mt-2">
          <span className="field-label">{copy.elements}</span>
          <ul className="mt-1 grid gap-1">
            {finding.elements.map((element, index) => (
              <li key={index} className="flex flex-wrap items-start gap-2 text-[10px]">
                <Pill tone={elementTone[element.status]}>{copy.elementStatus[element.status]}</Pill>
                <span className="min-w-0 flex-1 break-words text-[color:var(--color-text)]">
                  {element.element}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <TextList title={copy.reasons} items={finding.reasons} />
    </li>
  );
}

function MoveNode({ move, copy }: { move: StrategyMove; copy: AiCopy }) {
  return (
    <li className="mt-2">
      <details className="rounded-md border border-[color:var(--color-border)] px-3 py-2">
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-center gap-2">
            <Pill tone="bg-[color:var(--color-surface)] text-[color:var(--color-muted)]">
              {copy.actor[move.actor]}
            </Pill>
            <span className="min-w-0 flex-1 break-words text-[10px] font-semibold text-[color:var(--color-ink)]">
              {move.move}
            </span>
            <StrengthBadge strength={move.strength} copy={copy} />
            <VerificationBadge verification={move.verification} copy={copy} />
          </div>
        </summary>
        <p className="mt-2 text-[9px] text-[color:var(--color-muted)]">
          {copy.risk}: {copy.level[move.risk]} · {copy.cost}: {copy.level[move.cost]} · {copy.time}:{" "}
          {copy.level[move.time]}
        </p>
        {move.legalBasis.length > 0 ? (
          <div className="mt-2">
            <span className="field-label">{copy.legalBasis}</span>
            {move.legalBasis.map((citation, index) => (
              <CitationLine key={index} citation={citation} copy={copy} />
            ))}
          </div>
        ) : null}
        <TextList title={copy.requirements} items={move.requirements} />
        <TextList title={copy.reasons} items={move.reasons} />
        {move.children.length > 0 ? (
          <ul className="ml-3 border-l border-[color:var(--color-border)] pl-3">
            {move.children.map((child) => (
              <MoveNode key={child.id} move={child} copy={copy} />
            ))}
          </ul>
        ) : null}
      </details>
    </li>
  );
}

export function AnalysisPanel({
  caseId,
  analysis,
  strategy,
  language,
  copy,
  locked,
  demo,
}: {
  caseId: string;
  analysis: CaseAnalysis | null;
  strategy: StrategyTree | null;
  language: Language;
  copy: AiCopy;
  locked: boolean;
  demo: boolean;
}) {
  const disabled = locked || demo;
  return (
    <>
      <div className="panel col-span-full">
        <div className="panel-head">
          <div>
            <h2>{copy.analysisTitle}</h2>
            <p>{copy.analysisSub}</p>
          </div>
          {analysis ? (
            <span className="count-chip">
              {format(copy.version, { number: numberFor(language, analysis.version) })}
            </span>
          ) : null}
        </div>
        {demo ? (
          <p className="mt-3 text-[10px] text-[color:var(--color-muted)]">{copy.demoOnly}</p>
        ) : null}

        {analysis ? (
          <>
            <DraftNotice copy={copy} aiMock={analysis.aiMock} provider={analysis.provider} />
            {analysis.keywordOnly ? (
              <p role="status" className="mt-3 text-[10px] font-semibold text-[#806b43]">
                {copy.keywordOnly}
              </p>
            ) : null}
            {analysis.status !== "succeeded" ? (
              <p className="mt-3 text-[10px] font-semibold text-[#806b43]">
                {copy.insufficient}
                {analysis.abstainReason ? ` — ${analysis.abstainReason}` : ""}
              </p>
            ) : null}
            <ul className="mt-3">
              {analysis.findings.map((finding, index) => (
                <FindingCard key={index} finding={finding} copy={copy} />
              ))}
            </ul>
            <TextList title={copy.missingInfo} items={analysis.missingInformation} />
            <p className="mt-2 text-[9px] text-[color:var(--color-muted)]">{analysis.precedentNote}</p>
          </>
        ) : (
          <p className="mt-4 text-[10px] text-[color:var(--color-muted)]">{copy.noAnalysis}</p>
        )}

        <div className="mt-4 flex justify-end">
          <RunButton action={runAnalysisAction} caseId={caseId} label={copy.runAnalysis} disabled={disabled} />
        </div>
      </div>

      <div className="panel col-span-full">
        <div className="panel-head">
          <div>
            <h2>{copy.strategyTitle}</h2>
            <p>{copy.strategySub}</p>
          </div>
          {strategy ? (
            <span className="count-chip">
              {format(copy.version, { number: numberFor(language, strategy.version) })}
            </span>
          ) : null}
        </div>

        {strategy ? (
          <>
            <DraftNotice copy={copy} aiMock={strategy.aiMock} provider={strategy.provider} />
            {strategy.status !== "succeeded" ? (
              <p className="mt-3 text-[10px] font-semibold text-[#806b43]">{copy.insufficient}</p>
            ) : null}
            <ul className="mt-2">
              {strategy.moves.map((move) => (
                <MoveNode key={move.id} move={move} copy={copy} />
              ))}
            </ul>
            <TextList title={copy.missingInfo} items={strategy.missingInformation} />
            <p className="mt-2 text-[9px] text-[color:var(--color-muted)]">{strategy.precedentNote}</p>
          </>
        ) : (
          <p className="mt-4 text-[10px] text-[color:var(--color-muted)]">{copy.noStrategy}</p>
        )}

        <div className="mt-4 flex justify-end">
          <RunButton
            action={runStrategyAction}
            caseId={caseId}
            label={copy.runStrategy}
            disabled={disabled || !analysis}
          />
        </div>
      </div>
    </>
  );
}
