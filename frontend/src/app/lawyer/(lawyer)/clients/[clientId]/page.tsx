import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Icon } from "@/components/Icon";
import { ResetPasswordButton } from "@/components/lawyer/ResetPasswordButton";
import { getClientDetail } from "@/lib/api/lawyer";
import {
  dictionaries,
  numberFor,
  pick,
  titleFor,
} from "@/lib/i18n";
import { getLanguage } from "@/lib/language";

export async function generateMetadata(): Promise<Metadata> {
  const language = await getLanguage();
  return { title: titleFor(language, "lawyerClientDetail") };
}

export default async function ClientDetailPage({
  params,
}: {
  params: Promise<{ clientId: string }>;
}) {
  const { clientId } = await params;
  const language = await getLanguage();
  const copy = dictionaries[language];
  const client = getClientDetail(clientId);

  if (!client) notFound();

  return (
    <>
      <Link className="back-link" href="/lawyer/clients">
        <Icon name="arrow" size={15} />
        {copy.clientDetail.back}
      </Link>

      <div className="case-hero">
        <div>
          <span className="case-id">{client.id}</span>
          <h1>{pick(client.name, language)}</h1>
          <p>
            <Icon name="user" size={16} />
            {client.phone} <span>•</span> {client.email}
          </p>
        </div>
        <div className="hearing-badge">
          <small>{copy.clientDetail.casesLabel}</small>
          <b>{numberFor(language, client.cases.length)}</b>
        </div>
      </div>

      <p className="mock-note">{copy.common.mockData}</p>

      <div className="panel matters-panel">
        <div className="panel-head padded">
          <div>
            <h2>{copy.clientDetail.casesTitle}</h2>
            <p>{copy.clientDetail.casesSub}</p>
          </div>
          <ResetPasswordButton language={language} />
        </div>

        {client.cases.length ? (
          <div className="client-case-table">
            <div className="table-row table-header">
              <span>{copy.clientDetail.columns.matter}</span>
              <span>{copy.clientDetail.columns.court}</span>
              <span>{copy.clientDetail.columns.hearing}</span>
              <span>{copy.clientDetail.columns.status}</span>
            </div>
            {client.cases.map((matter) => (
              <div className="table-row" key={matter.id}>
                <span className="matter-cell">
                  <small>{matter.id}</small>
                  <b>{pick(matter.title, language)}</b>
                </span>
                <span data-label={copy.clientDetail.columns.court}>
                  {pick(matter.court, language)}
                </span>
                <span data-label={copy.clientDetail.columns.hearing}>
                  <b className="hearing-number">
                    #{numberFor(language, matter.hearingNumber)}
                  </b>
                </span>
                <span data-label={copy.clientDetail.columns.status}>
                  <em
                    className={`status ${matter.status === "closed" ? "status-closed" : ""}`}
                  >
                    <span /> {copy.matters.status[matter.status]}
                  </em>
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <Icon name="briefcase" />
            <b>{copy.clientDetail.noCases}</b>
          </div>
        )}
      </div>
    </>
  );
}
