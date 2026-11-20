import type { Metadata } from "next";
import { PageHeading } from "@/components/lawyer/PageHeading";
import { NewClientForm } from "@/components/lawyer/NewClientForm";
import { dictionaries, titleFor } from "@/lib/i18n";
import { getLanguage } from "@/lib/language";
import { isMockAuthEnabled } from "@/lib/session";

export async function generateMetadata(): Promise<Metadata> {
  const language = await getLanguage();
  return { title: titleFor(language, "lawyerNewClient") };
}

export default async function NewClientPage() {
  const language = await getLanguage();
  const copy = dictionaries[language];

  return (
    <>
      <PageHeading
        eyebrow={copy.newClient.eyebrow}
        title={copy.newClient.title}
        subtitle={copy.newClient.subtitle}
      />
      {isMockAuthEnabled() ? <p className="mock-note">{copy.common.mockData}</p> : null}
      <NewClientForm language={language} />
    </>
  );
}
