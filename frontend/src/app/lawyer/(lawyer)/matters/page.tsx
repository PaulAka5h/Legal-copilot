import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { MattersTable } from "@/components/lawyer/MattersTable";
import { PageHeading } from "@/components/lawyer/PageHeading";
import { listMatters } from "@/lib/api/lawyer";
import { dictionaries, titleFor } from "@/lib/i18n";
import { getLanguage } from "@/lib/language";
import { usedDemoData } from "@/lib/api/backendClient";

export async function generateMetadata(): Promise<Metadata> {
  const language = await getLanguage();
  return { title: titleFor(language, "lawyerMatters") };
}

export default async function LawyerMattersPage({
  searchParams,
}: {
  searchParams: Promise<{ showArchived?: string; archivedCase?: string }>;
}) {
  const { showArchived, archivedCase } = await searchParams;
  const includeArchived = showArchived === "1";
  const language = await getLanguage();
  const copy = dictionaries[language];
  const matters = await listMatters(includeArchived);

  return (
    <>
      <PageHeading
        eyebrow={copy.matters.eyebrow}
        title={copy.matters.title}
        subtitle={copy.matters.subtitle}
        action={
          <Link className="primary-button fit" href="/lawyer/matters/new">
            <Icon name="plus" size={18} />
            {copy.matters.newCase}
          </Link>
        }
      />
      {usedDemoData() ? <p className="mock-note">{copy.common.mockData}</p> : null}
      {archivedCase ? (
        <p className="success-note" role="status">
          {copy.caseDetail.archive.done}
        </p>
      ) : null}
      <p className="archived-toggle">
        <Link
          className="outline-button small"
          href={includeArchived ? "/lawyer/matters" : "/lawyer/matters?showArchived=1"}
        >
          {includeArchived ? copy.matters.hideArchived : copy.matters.showArchived}
        </Link>
      </p>
      <MattersTable language={language} matters={matters} />
    </>
  );
}
