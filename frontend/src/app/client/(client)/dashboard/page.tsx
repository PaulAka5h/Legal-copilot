import type { Metadata } from "next";
import Link from "next/link";
import {
  CaseProgress,
  progressFor,
  type CaseProgressStage,
} from "@/components/CaseProgress";
import { ClientDocuments } from "@/components/client/ClientDocuments";
import { Icon } from "@/components/Icon";
import { PageHeading } from "@/components/lawyer/PageHeading";
import {
  fetchClientDocuments,
  fetchClientHearing,
  fetchClientUpdates,
  getClientCase,
  listBackendClientCases,
  type BackendClientHearing,
  type BackendClientDocument,
  type BackendClientUpdate,
} from "@/lib/api/client";
import {
  dictionaries,
  format,
  numberFor,
  pick,
  titleFor,
} from "@/lib/i18n";
import { getLanguage } from "@/lib/language";
import { isMockAuthEnabled } from "@/lib/session";

export async function generateMetadata(): Promise<Metadata> {
  const language = await getLanguage();
  return { title: titleFor(language, "clientDashboard") };
}

function adaptHearing(hearing: BackendClientHearing | null) {
  if (!hearing) return null;
  const date = new Date(hearing.scheduled_at);
  return {
    day: date.getDate(),
    month: { en: date.toLocaleDateString("en-GB", { month: "short" }), bn: date.toLocaleDateString("bn-BD", { month: "short" }) },
    year: date.getFullYear(),
    place: { en: hearing.court_room || "—", bn: hearing.court_room || "—" },
    dateLabel: { en: hearing.purpose || "Hearing", bn: hearing.purpose || "শুনানি" },
  };
}

function adaptDocuments(docs: BackendClientDocument[]) {
  return docs.map((doc) => ({
    id: doc.id,
    format: "PDF" as const,
    name: { en: doc.display_name, bn: doc.display_name },
    size: { en: "—", bn: "—" },
    sharedOn: { en: new Date(doc.shared_at).toLocaleDateString("en-GB"), bn: new Date(doc.shared_at).toLocaleDateString("bn-BD") },
  }));
}

function adaptUpdates(updates: BackendClientUpdate[]) {
  return updates.map((update) => ({
    id: update.id,
    title: { en: update.title, bn: update.title },
    excerpt: { en: update.body.slice(0, 120), bn: update.body.slice(0, 120) },
    publishedOn: { en: update.published_at ? new Date(update.published_at).toLocaleDateString("en-GB") : "—", bn: update.published_at ? new Date(update.published_at).toLocaleDateString("bn-BD") : "—" },
  }));
}

function adaptLawyerContact() {
  return {
    name: { en: "Your Lawyer", bn: "আপনার আইনজীবী" },
    firm: { en: "—", bn: "—" },
    phone: "—",
    email: "—",
  };
}

export default async function ClientDashboardPage() {
  const language = await getLanguage();
  const copy = dictionaries[language];
  const dashboard = copy.clientDashboard;
  const mock = isMockAuthEnabled();

  if (mock) {
    const caseData = getClientCase();

    const stages: CaseProgressStage[] = caseData.stages.map((stage) => ({
      id: stage.id,
      label: pick(stage.label, language),
      note: pick(stage.note, language),
      state: stage.state,
    }));
    const { reached, total, percent } = progressFor(stages);
    const nextHearing = caseData.nextHearing;

    return (
      <>
        <PageHeading
          eyebrow={dashboard.eyebrow}
          title={dashboard.title}
          subtitle={dashboard.subtitle}
        />

        <p className="mock-note">{copy.common.mockData}</p>

        <div className="case-hero">
          <div>
            <span className="case-id">
              {caseData.id} <i>{pick(caseData.statusLabel, language)}</i>
            </span>
            <h1>{pick(caseData.title, language)}</h1>
            <p>
              <Icon name="briefcase" size={16} />
              {pick(caseData.caseType, language)} <span>•</span>{" "}
              {pick(caseData.court, language)}
            </p>
          </div>
          <div className="hearing-badge">
            <small>{dashboard.currentStage}</small>
            <b>
              {format(dashboard.hearing, {
                number: numberFor(language, caseData.hearingNumber),
              })}
            </b>
          </div>
        </div>

        <div className="case-layout">
          <div className="panel progress-panel">
            <div className="panel-head">
              <div>
                <h2>{dashboard.progressTitle}</h2>
                <p>
                  {format(dashboard.progressSub, {
                    reached: numberFor(language, reached),
                    total: numberFor(language, total),
                  })}
                </p>
              </div>
              <span className="percent">
                {format(dashboard.percent, {
                  value: numberFor(language, percent),
                })}
              </span>
            </div>
            <CaseProgress
              language={language}
              stages={stages}
              completeLabel={dashboard.complete}
            />
          </div>

          {nextHearing ? (
            <div className="next-hearing">
              <div className="calendar-large">
                <small>{pick(nextHearing.month, language)}</small>
                <b>{numberFor(language, nextHearing.day)}</b>
                <span>{numberFor(language, nextHearing.year)}</span>
              </div>
              <div>
                <span className="eyebrow">{dashboard.nextHearing}</span>
                <h2>{pick(nextHearing.dateLabel, language)}</h2>
                <p>{pick(nextHearing.place, language)}</p>
                <small className="lawyer-entered">{dashboard.lawyerEntered}</small>
              </div>
            </div>
          ) : (
            <div className="panel empty-note">{dashboard.noHearing}</div>
          )}

          <div className="panel lawyer-panel">
            <div className="panel-head">
              <div>
                <h2>{pick(caseData.lawyer.name, language)}</h2>
                <p>{dashboard.lawyerSub}</p>
              </div>
            </div>
            <dl className="profile-list">
              <div>
                <dt>{dashboard.firm}</dt>
                <dd>{pick(caseData.lawyer.firm, language)}</dd>
              </div>
              <div>
                <dt>{dashboard.phone}</dt>
                <dd>
                  <a href={`tel:${caseData.lawyer.phone}`}>{caseData.lawyer.phone}</a>
                </dd>
              </div>
              <div>
                <dt>{dashboard.email}</dt>
                <dd>
                  <a href={`mailto:${caseData.lawyer.email}`}>{caseData.lawyer.email}</a>
                </dd>
              </div>
            </dl>
          </div>

          <div className="panel docs-panel">
            <div className="panel-head">
              <div>
                <h2>{dashboard.documentsTitle}</h2>
                <p>{dashboard.documentsSub}</p>
              </div>
              <span className="count-chip">
                {format(dashboard.files, {
                  count: numberFor(language, caseData.documents.length),
                })}
              </span>
            </div>
            <ClientDocuments
              documents={caseData.documents}
              language={language}
              download={dashboard.download}
              notice={dashboard.downloadMock}
            />
          </div>

          <div className="panel summaries-panel">
            <div className="panel-head">
              <div>
                <h2>{dashboard.summariesTitle}</h2>
                <p>{dashboard.summariesSub}</p>
              </div>
              <span className="count-chip">
                {format(dashboard.summariesCount, {
                  count: numberFor(language, caseData.summaries.length),
                })}
              </span>
            </div>
            {caseData.summaries.length ? (
              <div className="summary-list">
                {caseData.summaries.map((summary) => (
                  <Link
                    className="summary-row"
                    key={summary.id}
                    href={`/client/summaries/${summary.id}`}
                  >
                    <span>
                      <b>{pick(summary.title, language)}</b>
                      <p>{pick(summary.excerpt, language)}</p>
                      <small>{pick(summary.publishedOn, language)}</small>
                    </span>
                    <span>
                      <em className="approved-badge">{dashboard.approved}</em>
                      <Icon name="chevron" size={18} />
                    </span>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="empty-note">{dashboard.noSummaries}</p>
            )}
            <p className="summary-note">{dashboard.onlyApproved}</p>
          </div>
        </div>
      </>
    );
  }

  // Real backend mode
  const cases = await listBackendClientCases();

  if (cases.length === 0) {
    return (
      <>
        <PageHeading eyebrow={dashboard.eyebrow} title={dashboard.title} subtitle={dashboard.subtitle} />
        <p className="empty-note">{dashboard.realEmpty}</p>
        <p className="panel empty-note">{dashboard.laterUnavailable}</p>
      </>
    );
  }

  // If multiple cases, show a case picker (for now, pick the first one)
  const caseId = cases[0].id;

  // Fetch all case details in parallel
  const [hearing, documents, updates] = await Promise.all([
    fetchClientHearing(caseId),
    fetchClientDocuments(caseId),
    fetchClientUpdates(caseId),
  ]);

  const adaptedHearing = adaptHearing(hearing);
  const adaptedDocuments = adaptDocuments(documents);
  const adaptedUpdates = adaptUpdates(updates);
  const adaptedLawyer = adaptLawyerContact();

  // For stages, we need to get them from the case - use mock stages for now
  // since backend doesn't expose client_visible_case_fields yet
  const mockCaseData = getClientCase();
  const stages: CaseProgressStage[] = mockCaseData.stages.map((stage) => ({
    id: stage.id,
    label: pick(stage.label, language),
    note: pick(stage.note, language),
    state: stage.state,
  }));
  const { reached, total, percent } = progressFor(stages);

  return (
    <>
      <PageHeading
        eyebrow={dashboard.eyebrow}
        title={dashboard.title}
        subtitle={dashboard.subtitle}
      />

      <div className="case-hero">
        <div>
          <span className="case-id">
            {cases[0].id} <i>{cases[0].status}</i>
          </span>
          <h1>{cases[0].title}</h1>
          <p>
            <Icon name="briefcase" size={16} />
            {cases[0].case_type} <span>•</span>{" "}
            {cases[0].court || "—"}
          </p>
        </div>
        <div className="hearing-badge">
          <small>{dashboard.currentStage}</small>
          <b>
            {format(dashboard.hearing, {
              number: numberFor(language, 1),
            })}
          </b>
        </div>
      </div>

      <div className="case-layout">
        <div className="panel progress-panel">
          <div className="panel-head">
            <div>
              <h2>{dashboard.progressTitle}</h2>
              <p>
                {format(dashboard.progressSub, {
                  reached: numberFor(language, reached),
                  total: numberFor(language, total),
                })}
              </p>
            </div>
            <span className="percent">
              {format(dashboard.percent, {
                value: numberFor(language, percent),
              })}
            </span>
          </div>
          <CaseProgress
            language={language}
            stages={stages}
            completeLabel={dashboard.complete}
          />
        </div>

        {adaptedHearing ? (
          <div className="next-hearing">
            <div className="calendar-large">
              <small>{pick(adaptedHearing.month, language)}</small>
              <b>{numberFor(language, adaptedHearing.day)}</b>
              <span>{numberFor(language, adaptedHearing.year)}</span>
            </div>
            <div>
              <span className="eyebrow">{dashboard.nextHearing}</span>
              <h2>{pick(adaptedHearing.dateLabel, language)}</h2>
              <p>{pick(adaptedHearing.place, language)}</p>
              <small className="lawyer-entered">{dashboard.lawyerEntered}</small>
            </div>
          </div>
        ) : (
          <div className="panel empty-note">{dashboard.noHearing}</div>
        )}

        <div className="panel lawyer-panel">
          <div className="panel-head">
            <div>
              <h2>{pick(adaptedLawyer.name, language)}</h2>
              <p>{dashboard.lawyerSub}</p>
            </div>
          </div>
          <dl className="profile-list">
            <div>
              <dt>{dashboard.firm}</dt>
              <dd>{pick(adaptedLawyer.firm, language)}</dd>
            </div>
            <div>
              <dt>{dashboard.phone}</dt>
              <dd>
                <a href={`tel:${adaptedLawyer.phone}`}>{adaptedLawyer.phone}</a>
              </dd>
            </div>
            <div>
              <dt>{dashboard.email}</dt>
              <dd>
                <a href={`mailto:${adaptedLawyer.email}`}>{adaptedLawyer.email}</a>
              </dd>
            </div>
          </dl>
        </div>

        <div className="panel docs-panel">
          <div className="panel-head">
            <div>
              <h2>{dashboard.documentsTitle}</h2>
              <p>{dashboard.documentsSub}</p>
            </div>
            <span className="count-chip">
              {format(dashboard.files, {
                count: numberFor(language, adaptedDocuments.length),
              })}
            </span>
          </div>
          <ClientDocuments
            documents={adaptedDocuments}
            language={language}
            download={dashboard.download}
            notice={dashboard.downloadMock}
          />
        </div>

        <div className="panel summaries-panel">
          <div className="panel-head">
            <div>
              <h2>{dashboard.summariesTitle}</h2>
              <p>{dashboard.summariesSub}</p>
            </div>
            <span className="count-chip">
              {format(dashboard.summariesCount, {
                count: numberFor(language, adaptedUpdates.length),
              })}
            </span>
          </div>
          {adaptedUpdates.length ? (
            <div className="summary-list">
              {adaptedUpdates.map((summary) => (
                <Link
                  className="summary-row"
                  key={summary.id}
                  href={`/client/summaries/${summary.id}`}
                >
                  <span>
                    <b>{pick(summary.title, language)}</b>
                    <p>{pick(summary.excerpt, language)}</p>
                    <small>{pick(summary.publishedOn, language)}</small>
                  </span>
                  <span>
                    <em className="approved-badge">{dashboard.approved}</em>
                    <Icon name="chevron" size={18} />
                  </span>
                </Link>
              ))}
            </div>
          ) : (
            <p className="empty-note">{dashboard.noSummaries}</p>
          )}
          <p className="summary-note">{dashboard.onlyApproved}</p>
        </div>
      </div>
    </>
  );
}
