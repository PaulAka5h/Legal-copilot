import type { Metadata } from "next";
import Link from "next/link";
import { createMatterAction } from "@/app/lawyer/actions";
import { Field } from "@/components/Field";
import { Icon } from "@/components/Icon";
import { PageHeading } from "@/components/lawyer/PageHeading";
import { listCaseTypes, listClients, listCourts } from "@/lib/api/lawyer";
import { dictionaries, pick, titleFor } from "@/lib/i18n";
import { getLanguage } from "@/lib/language";

export async function generateMetadata(): Promise<Metadata> {
  const language = await getLanguage();
  return { title: titleFor(language, "lawyerNewMatter") };
}

export default async function NewMatterPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const language = await getLanguage();
  const copy = dictionaries[language];
  const { error } = await searchParams;
  const clients = listClients();
  const courts = listCourts();
  const caseTypes = listCaseTypes();

  return (
    <>
      <PageHeading
        eyebrow={copy.newMatter.eyebrow}
        title={copy.newMatter.title}
        subtitle={copy.newMatter.subtitle}
      />
      <p className="mock-note">{copy.common.mockData}</p>

      <form className="panel client-form" action={createMatterAction}>
        <p className="mock-note">{copy.newMatter.mockNote}</p>
        {error ? (
          <p className="form-error" role="alert">
            {copy.newMatter.error}
          </p>
        ) : null}

        <div className="form-section-head">
          <span>01</span>
          <div>
            <h2>{copy.newMatter.sectionTitle}</h2>
            <p>{copy.newMatter.sectionBody}</p>
          </div>
        </div>

        <div className="form-grid">
          <div className="full">
            <Field label={copy.newMatter.caseTitle}>
              <input
                name="title"
                required
                placeholder={copy.newMatter.caseTitlePlaceholder}
              />
            </Field>
          </div>

          <label className="field">
            <span className="field-label">{copy.newMatter.court}</span>
            <select name="court" required defaultValue="">
              <option value="" disabled>
                {copy.newMatter.selectCourt}
              </option>
              {courts.map((court) => (
                <option key={court.en} value={court.en}>
                  {pick(court, language)}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span className="field-label">{copy.newMatter.caseType}</span>
            <select name="caseType" required defaultValue="">
              <option value="" disabled>
                {copy.newMatter.selectType}
              </option>
              {caseTypes.map((caseType) => (
                <option key={caseType.en} value={caseType.en}>
                  {pick(caseType, language)}
                </option>
              ))}
            </select>
          </label>

          <label className="field full">
            <span className="field-label">{copy.newMatter.client}</span>
            <select name="clientId" required defaultValue="">
              <option value="" disabled>
                {copy.newMatter.selectClient}
              </option>
              {clients.map((client) => (
                <option key={client.id} value={client.id}>
                  {pick(client.name, language)}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="form-actions">
          <Link className="ghost-button" href="/lawyer/matters">
            {copy.newMatter.cancel}
          </Link>
          <button className="primary-button fit" type="submit">
            {copy.newMatter.save}
            <Icon name="arrow" size={18} />
          </button>
        </div>
      </form>
    </>
  );
}
