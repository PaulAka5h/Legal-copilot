import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { updateMatterStageAction } from "@/app/lawyer/actions";
import {
  CaseProgress,
  progressFor,
  type CaseProgressStage,
} from "@/components/CaseProgress";
import { Icon } from "@/components/Icon";
import { MatterWorkspace } from "@/components/lawyer/MatterWorkspace";
import {
  getCase,
  getBackendMatter,
  listDocuments,
  listHearings,
  type Matter,
} from "@/lib/api/lawyer";
import {
  dictionaries,
  format,
  numberFor,
  pick,
  titleFor,
  type Dictionary,
  type Language,
} from "@/lib/i18n";
import { getLanguage } from "@/lib/language";
import { isMockAuthEnabled } from "@/lib/session";

export async function generateMetadata(): Promise<Metadata> {
  const language = await getLanguage();
  return { title: titleFor(language, "lawyerCaseDetail") };
}

function stagesFor(
  matter: Matter,
  language: Language,
  copy: Dictionary["caseDetail"],
): CaseProgressStage[] {
  const currentIndex = Math.max(
    0,
    matter.stages.findIndex((stage) => stage.id === matter.currentStageId),
  );
  const closed = matter.status === "closed";

  return matter.stages.map((stage, index) => {
    const complete = closed || index < currentIndex;
    const current = !complete && index === currentIndex;

    return {
      id: stage.id,
      label: pick(stage.label, language),
      note: complete
        ? stage.date
          ? pick(stage.date, language)
          : copy.complete
        : current
          ? copy.inProgress
          : copy.upcoming,
      state: complete ? "complete" : current ? "current" : "upcoming",
    };
  });
}

export default async function LawyerMatterPage({
  params,
  searchParams,
}: {
  params: Promise<{ caseId: string }>;
  searchParams: Promise<{ hearingError?: string; noteError?: string }>;
}) {
  const { caseId } = await params;
  const { hearingError, noteError } = await searchParams;
  const language = await getLanguage();
  const copy = dictionaries[language];
  const mock = isMockAuthEnabled();
  const matter = mock ? getCase(caseId) : await getBackendMatter(caseId);

  if (!matter) notFound();

  const stages = stagesFor(matter, language, copy.caseDetail);
  const hearings = listHearings(caseId);
  const { reached, total, percent } = progressFor(stages);
  const locked = matter.status === "closed";
  const hearingFormError = hearingError
    ? "hearing"
    : noteError
      ? "note"
      : null;

  return (
    <>
      <Link className="back-link" href="/lawyer/matters">
        <Icon name="arrow" size={15} />
        {copy.caseDetail.back}
      </Link>

      <div className="case-hero">
        <div>
          <span className="case-id">
            {matter.id} <i>{copy.matters.status[matter.status]}</i>
          </span>
          <h1>{pick(matter.title, language)}</h1>
          <p>
            <Icon name="briefcase" size={16} />
            {pick(matter.caseType, language)} <span>•</span>{" "}
            {pick(matter.court, language)}
          </p>
          <p>
            <Icon name="user" size={16} />
            {pick(matter.clientName, language)}
          </p>
        </div>

        {mock ? <div className="stage-picker">
          <label className="stage-label" htmlFor="case-stage">
            {copy.caseDetail.stageLabel}
          </label>
          <form action={updateMatterStageAction}>
            <input type="hidden" name="caseId" value={matter.id} />
            <select
              id="case-stage"
              name="stageId"
              defaultValue={matter.currentStageId}
              disabled={locked}
            >
              {matter.stages.map((stage) => (
                <option key={stage.id} value={stage.id}>
                  {pick(stage.label, language)}
                </option>
              ))}
            </select>
            <button type="submit" disabled={locked}>
              {copy.caseDetail.saveStage}
            </button>
          </form>
          <span className="stage-help">
            {locked ? copy.caseDetail.stageLocked : copy.caseDetail.stageHelp}
          </span>
          <span className="stage-hearing">
            {format(copy.caseDetail.hearing, {
              number: numberFor(language, matter.hearingNumber),
            })}
          </span>
        </div> : <div className="stage-picker"><span className="stage-help">{copy.caseDetail.notAvailableYet}</span></div>}
      </div>

      {mock ? <p className="mock-note">{copy.common.mockData}</p> : null}

      <div className="case-layout">
        <div className="panel progress-panel">
          <div className="panel-head">
            <div>
              <h2>{copy.caseDetail.progressTitle}</h2>
              <p>
                {format(copy.caseDetail.progressSub, {
                  reached: numberFor(language, reached),
                  total: numberFor(language, total),
                })}
              </p>
            </div>
            <span className="percent">
              {format(copy.caseDetail.percent, {
                value: numberFor(language, percent),
              })}
            </span>
          </div>
          <CaseProgress
            language={language}
            stages={stages}
            completeLabel={copy.caseDetail.complete}
          />
        </div>

        {mock ? (
          <MatterWorkspace
            key={matter.id}
            caseId={matter.id}
            hearings={hearings}
            initialDocuments={listDocuments(caseId)}
            language={language}
            copy={copy.caseDetail}
            locked={locked}
            error={hearingFormError}
          />
        ) : (
          <div className="panel empty-note">{copy.caseDetail.notAvailableYet}</div>
        )}
      </div>
    </>
  );
}
