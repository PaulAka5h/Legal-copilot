import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { archiveMatterAction } from "@/app/lawyer/actions";
import {
  CaseProgress,
  progressFor,
  type CaseProgressStage,
} from "@/components/CaseProgress";
import { Icon } from "@/components/Icon";
import { ArchiveCaseDialog } from "@/components/lawyer/ArchiveCaseDialog";
import { ClientAccessPanel } from "@/components/lawyer/ClientAccessPanel";
import { EditCasePanel } from "@/components/lawyer/EditCasePanel";
import {
  MatterWorkspace,
  type WorkspaceNotice,
  type WorkspaceTab,
} from "@/components/lawyer/MatterWorkspace";
import { usedDemoData } from "@/lib/api/backendClient";
import {
  getCase,
  getCaseIntelligence,
  listDocuments,
  listCaseTypes,
  listCourts,
  listHearings,
  listLinkableClients,
  type LinkClientResult,
  type Matter,
} from "@/lib/api/lawyer";
import {
  dictionaries,
  format,
  numberFor,
  pick,
  titleFor,
  type Dictionary,
} from "@/lib/i18n";
import { getLanguage } from "@/lib/language";

export async function generateMetadata(): Promise<Metadata> {
  const language = await getLanguage();
  return { title: titleFor(language, "lawyerCaseDetail") };
}

/** Progress comes from the backend (hearings and status), never a hand-set stage. */
function stagesFor(matter: Matter, copy: Dictionary["caseDetail"]): CaseProgressStage[] {
  const notes = { complete: copy.complete, current: copy.inProgress, upcoming: copy.upcoming };
  return matter.progress.map((stage) => ({
    id: stage.id,
    label: copy.stages[stage.id],
    note: notes[stage.state],
    state: stage.state,
  }));
}

export default async function LawyerMatterPage({
  params,
  searchParams,
}: {
  params: Promise<{ caseId: string }>;
  searchParams: Promise<{
    hearingError?: string;
    noteError?: string;
    edit?: string;
    edited?: string;
    editError?: string;
    archiveError?: string;
    restored?: string;
    tab?: string;
    ai?: string;
    detail?: string;
    clientLink?: string;
  }>;
}) {
  const { caseId } = await params;
  const {
    hearingError,
    noteError,
    edit,
    edited,
    editError,
    archiveError,
    restored,
    tab,
    ai,
    detail,
    clientLink,
  } = await searchParams;
  const language = await getLanguage();
  const copy = dictionaries[language];
  const matter = await getCase(caseId);

  if (!matter) notFound();

  const stages = stagesFor(matter, copy.caseDetail);
  const [hearings, intelligence, linkableClients] = await Promise.all([
    listHearings(caseId),
    getCaseIntelligence(caseId),
    listLinkableClients(),
  ]);
  const linkResults: LinkClientResult[] = ["ok", "no_login", "error", "NOT_CONFIGURED"];
  const clientLinkResult = linkResults.find((value) => value === clientLink) ?? null;
  const documents = await listDocuments(caseId, hearings);
  const demo = usedDemoData();
  const initialTab: WorkspaceTab =
    tab === "documents" || tab === "facts" || tab === "analysis"
      ? tab
      : "hearings";
  const notice: WorkspaceNotice =
    ai === "ok" || ai === "error" || ai === "NOT_CONFIGURED"
      ? { status: ai, detail: detail ?? "" }
      : null;
  const { reached, total, percent } = progressFor(stages);
  const locked = matter.status === "closed" || matter.archived;
  const editing = edit === "1" && !matter.archived;
  const notices = [
    edited ? copy.caseDetail.edit.saved : null,
    restored ? copy.caseDetail.archive.restored : null,
  ].filter(Boolean);
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

        <div className="stage-picker">
          <span className="stage-hearing">
            {format(copy.caseDetail.hearing, {
              number: numberFor(language, matter.hearingNumber),
            })}
          </span>
          <div className="case-actions">
            {matter.archived ? (
              matter.isLead ? (
                <form action={archiveMatterAction}>
                  <input type="hidden" name="caseId" value={matter.id} />
                  <input type="hidden" name="archive" value="0" />
                  <button type="submit" className="case-action">
                    {copy.caseDetail.archive.restore}
                  </button>
                </form>
              ) : null
            ) : (
              <>
                <Link className="case-action" href={`/lawyer/matters/${encodeURIComponent(matter.id)}?edit=1#edit-case`}>
                  {copy.caseDetail.edit.open}
                </Link>
                {matter.isLead ? (
                  <ArchiveCaseDialog caseId={matter.id} copy={copy.caseDetail.archive} />
                ) : null}
              </>
            )}
          </div>
          <span className="stage-help">
            {matter.archived
              ? copy.caseDetail.edit.archivedLocked
              : matter.isLead
                ? copy.caseDetail.progressHelp
                : copy.caseDetail.archive.leadOnly}
          </span>
        </div>
      </div>

      {demo ? <p className="mock-note">{copy.common.mockData}</p> : null}
      {matter.archived ? (
        <p className="mock-note" role="status">
          {copy.caseDetail.archive.banner}
        </p>
      ) : null}
      {archiveError ? (
        <p className="form-error" role="alert">
          {copy.caseDetail.archive.error}
        </p>
      ) : null}
      {notices.map((notice) => (
        <p className="success-note" role="status" key={notice}>
          {notice}
        </p>
      ))}
      {editing ? (
        <EditCasePanel
          matter={matter}
          language={language}
          copy={copy.caseDetail.edit}
          statusLabels={copy.matters.status}
          caseTypes={listCaseTypes()}
          courts={listCourts()}
          error={editError ?? null}
        />
      ) : null}

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

        <ClientAccessPanel
          caseId={matter.id}
          clients={linkableClients}
          locked={locked}
          result={clientLinkResult}
          copy={copy.caseDetail.clientAccess}
          notConfigured={copy.common.notAvailableYet}
        />

        <MatterWorkspace
          key={`${matter.id}-${initialTab}-${ai ?? ""}`}
          caseId={matter.id}
          hearings={hearings}
          initialDocuments={documents}
          language={language}
          copy={copy.caseDetail}
          locked={locked}
          error={hearingFormError}
          intelligence={intelligence}
          demo={demo}
          initialTab={initialTab}
          notice={notice}
        />
      </div>
    </>
  );
}
