import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { ClientsList } from "@/components/lawyer/ClientsList";
import { PageHeading } from "@/components/lawyer/PageHeading";
import { listClients } from "@/lib/api/lawyer";
import { dictionaries, titleFor } from "@/lib/i18n";
import { getLanguage } from "@/lib/language";

export async function generateMetadata(): Promise<Metadata> {
  const language = await getLanguage();
  return { title: titleFor(language, "lawyerClients") };
}

export default async function LawyerClientsPage() {
  const language = await getLanguage();
  const copy = dictionaries[language];
  const clients = listClients();

  return (
    <>
      <PageHeading
        eyebrow={copy.clients.eyebrow}
        title={copy.clients.title}
        subtitle={copy.clients.subtitle}
        action={
          <Link className="primary-button fit" href="/lawyer/clients/new">
            <Icon name="plus" size={18} />
            {copy.clients.newClient}
          </Link>
        }
      />
      <p className="mock-note">{copy.common.mockData}</p>
      <ClientsList language={language} clients={clients} />
    </>
  );
}
