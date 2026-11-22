import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { usedDemoData } from "@/lib/api/backendClient";
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
  searchParams,
}: {
  params: Promise<{ summaryId: string }>;
  searchParams: Promise<{ download?: string }>;
}) {
  const { summaryId } = await params;
  const { download } = await searchParams;
  const language = await getLanguage();
  const copy = dictionaries[language];
  const summary = await getApprovedSummary(summaryId);

  if (!summary) notFound();

  return (
    <>
      <Link className="back-link" href="/client/dashboard">
        <Icon name="arrow" size={15} />
        {copy.clientSummaries.back}
      </Link>

      <PageHeading
        eyebrow={copy.clientSummaries.eyebrow}
        title={pick(summary.title, language)}
        subtitle={copy.clientSummaries.subtitle}
      />

      {usedDemoData() ? <p className="mock-note">{copy.clientSummaries.mock}</p> : null}

      <article className="panel summary-detail">
        <div className="summary-meta">
          <span className="approved-badge">
            {copy.clientDashboard.approved}
          </span>
          <small>{pick(summary.publishedOn, language)}</small>
        </div>

        <div className="mt-5 grid gap-5">
          {summary.sections.map((section) => (
            <section
              key={section.id}
              className="border-t border-[color:var(--color-border)] pt-4 first:border-0 first:pt-0"
            >
              <h2 className="m-0 text-[13px] font-bold text-[color:var(--color-ink)]">
                {copy.clientSummaries.sections[section.id]}
              </h2>
              <p className="mt-1.5 text-[12px] leading-relaxed text-[#3c4347]">
                {pick(section.text, language)}
              </p>
            </section>
          ))}
        </div>

        <aside className="mt-6 rounded-lg border border-[#e8d9b5] bg-[#fbf6e9] px-4 py-3">
          <p className="text-[10px] leading-relaxed text-[#6b5326]">
            {copy.clientSummaries.notLegalAdvice}
          </p>
        </aside>

        <a
          className="outline-button small mt-4 inline-flex"
          id="download"
          href={`/client/summaries/${encodeURIComponent(summary.id)}/pdf`}
          download
        >
          <Icon name="download" size={14} />
          {copy.clientSummaries.download}
        </a>

        {download === "NOT_CONFIGURED" ? (
          <p
            className="mt-3 rounded-md border border-dashed border-[color:var(--color-border)] bg-[color:var(--color-surface)] px-3 py-2 text-[9px] font-semibold text-[color:var(--color-muted)]"
            role="status"
          >
            {copy.clientSummaries.downloadNotConfigured}
          </p>
        ) : null}
      </article>
    </>
  );
}
