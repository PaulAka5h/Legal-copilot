import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { MattersTable } from "@/components/lawyer/MattersTable";
import { PageHeading } from "@/components/lawyer/PageHeading";
import { listBackendMatters, listMatters } from "@/lib/api/lawyer";
import { dictionaries, titleFor } from "@/lib/i18n";
import { getLanguage } from "@/lib/language";
import { isMockAuthEnabled } from "@/lib/session";

export async function generateMetadata(): Promise<Metadata> {
  const language = await getLanguage();
  return { title: titleFor(language, "lawyerMatters") };
}

export default async function LawyerMattersPage() {
  const language = await getLanguage();
  const copy = dictionaries[language];
  const mock = isMockAuthEnabled();
  const matters = mock ? listMatters() : await listBackendMatters();

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
      {mock ? <p className="mock-note">{copy.common.mockData}</p> : null}
      <MattersTable language={language} matters={matters} />
    </>
  );
}
