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
import { SignOutButton } from "@/components/SignOutButton";
import { getClientCase } from "@/lib/api/client";
import {
  dictionaries,
  format,
  numberFor,
  pick,
  titleFor,
} from "@/lib/i18n";
import { getLanguage } from "@/lib/language";
import { usedDemoData } from "@/lib/api/backendClient";

export async function generateMetadata(): Promise<Metadata> {
  const language = await getLanguage();
  return { title: titleFor(language, "clientDashboard") };
}

export default async function ClientDashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ case?: string }>;
}) {
  const { case: caseId } = await searchParams;
  const language = await getLanguage();
  const copy = dictionaries[language];
  const dashboard = copy.clientDashboard;
  const caseData = await getClientCase(caseId);
  if (!caseData) {
    return (
      <div className="panel empty-state">
        <Icon name="briefcase" size={28} />
        <h1>{dashboard.noCaseTitle}</h1>
        <p>{dashboard.noCase}</p>
        <div className="empty-state-actions">
          <SignOutButton label={copy.common.signOut} />
        </div>
      </div>
    );
  }

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

      {usedDemoData() ? <p className="mock-note">{copy.common.mockData}</p> : null}

      {caseData.cases.length > 1 ? (
        <nav className="filter-pills case-switcher" aria-label={dashboard.yourCases}>
          {caseData.cases.map((item) => (
            <Link
              key={item.id}
              href={`/client/dashboard?case=${encodeURIComponent(item.id)}`}
              className={item.id === caseData.id ? "active" : ""}
              aria-current={item.id === caseData.id ? "page" : undefined}
            >
              {pick(item.title, language)}
            </Link>
          ))}
        </nav>
      ) : null}

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
          {/* Only the fields the lawyer filled in and allows clients to see. */}
          {caseData.lawyer.firm || caseData.lawyer.phone || caseData.lawyer.email ? (
            <dl className="profile-list">
              {caseData.lawyer.firm ? (
                <div>
                  <dt>{dashboard.firm}</dt>
                  <dd>{pick(caseData.lawyer.firm, language)}</dd>
                </div>
              ) : null}
              {caseData.lawyer.phone ? (
                <div>
                  <dt>{dashboard.phone}</dt>
                  <dd>
                    <a href={`tel:${caseData.lawyer.phone.replace(/[^0-9+]/g, "")}`}>{caseData.lawyer.phone}</a>
                  </dd>
                </div>
              ) : null}
              {caseData.lawyer.email ? (
                <div>
                  <dt>{dashboard.email}</dt>
                  <dd>
                    <a href={`mailto:${caseData.lawyer.email}`}>{caseData.lawyer.email}</a>
                  </dd>
                </div>
              ) : null}
            </dl>
          ) : null}
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
