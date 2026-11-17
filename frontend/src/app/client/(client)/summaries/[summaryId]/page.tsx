import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { PageHeading } from "@/components/lawyer/PageHeading";
import { getApprovedSummary } from "@/lib/api/client";
import { dictionaries, pick, titleFor } from "@/lib/i18n";
import { getLanguage } from "@/lib/language";

export async function generateMetadata(): Promise<Metadata> {
  const language = await getLanguage();
  return { title: titleFor(language, "clientSummary") };
}

export default async function ClientSummaryPage({
  params,
}: {
  params: Promise<{ summaryId: string }>;
}) {
  const { summaryId } = await params;
  const language = await getLanguage();
  const copy = dictionaries[language];
  const summary = getApprovedSummary(summaryId);

  return (
    <>
      <Link className="back-link" href="/client/dashboard">
        <Icon name="arrow" size={15} />
        {copy.clientSummaries.back}
      </Link>

      <PageHeading
        eyebrow={copy.clientSummaries.eyebrow}
        title={
          summary ? pick(summary.title, language) : copy.clientSummaries.notAvailable
        }
        subtitle={copy.clientSummaries.subtitle}
      />

      <p className="mock-note">{copy.clientSummaries.mock}</p>

      <div className="panel summary-detail">
        {summary ? (
          <>
            <div className="summary-meta">
              <span className="approved-badge">
                {copy.clientDashboard.approved}
              </span>
              <small>{pick(summary.publishedOn, language)}</small>
            </div>
            <p>{pick(summary.excerpt, language)}</p>
            <p className="empty-note">{copy.clientSummaries.placeholder}</p>
          </>
        ) : (
          <p className="empty-note">{copy.clientSummaries.notAvailableBody}</p>
        )}
      </div>
    </>
  );
}
