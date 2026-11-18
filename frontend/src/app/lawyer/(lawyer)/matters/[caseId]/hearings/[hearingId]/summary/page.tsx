import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  approveHearingSummaryAction,
  downloadHearingSummaryAction,
  saveHearingSummaryAction,
} from "@/app/lawyer/actions";
import { Icon } from "@/components/Icon";
import {
  getCase,
  getHearingSummary,
  getLawyerProfile,
  listHearings,
  type ClaimType,
  type HearingSummary,
  type SummarySection,
} from "@/lib/api/lawyer";
import {
  dictionaries,
  format,
  numberFor,
  pick,
  titleFor,
  type Dictionary,
  type Language,
} from "@/lib/i18n";
import { getLanguage } from "@/lib/language";

export async function generateMetadata(): Promise<Metadata> {
  const language = await getLanguage();
  return { title: titleFor(language, "lawyerHearingSummary") };
}

const claimTone: Record<ClaimType, string> = {
  document: "bg-[color:var(--color-pale)] text-[#26617f]",
  lawyer: "bg-[#eaf6ef] text-[var(--color-deep)]",
  ai: "bg-[#f5efe1] text-[#806b43]",
  assumption: "bg-[color:var(--color-surface)] text-[color:var(--color-muted)]",
};

const inputClass =
  "w-full rounded-[9px] border border-[color:var(--color-border)] bg-[color:var(--color-surface)] px-3 py-2 text-[11px] text-[color:var(--color-text)] outline-none focus:border-[color:var(--color-green)]";

function hearingDateLabel(date: string, language: Language) {
  const label = new Intl.DateTimeFormat(language === "bn" ? "bn-BD" : "en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${date}T00:00:00Z`));

  return language === "en" ? label.toUpperCase() : label;
}

function versionDateLabel(date: string, language: Language) {
  return new Intl.DateTimeFormat(language === "bn" ? "bn-BD" : "en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "UTC",
    timeZoneName: "short",
  }).format(new Date(date));
}

function MemoHeader({
  summary,
  language,
  copy,
}: {
  summary: HearingSummary;
  language: Language;
  copy: Dictionary["hearingSummary"];
}) {
  const profile = getLawyerProfile();

  return (
    <dl className="grid gap-x-6 gap-y-3 border-b border-[color:var(--color-border)] py-5 sm:grid-cols-2">
      <div>
        <dt className="text-[8px] font-bold uppercase tracking-[0.14em] text-[color:var(--color-muted)]">
          {copy.matter}
        </dt>
        <dd className="mt-1 text-[11px] font-semibold text-[color:var(--color-ink)]">
          {pick(summary.matterTitle, language)}
        </dd>
      </div>
      <div>
        <dt className="text-[8px] font-bold uppercase tracking-[0.14em] text-[color:var(--color-muted)]">
          {copy.client}
        </dt>
        <dd className="mt-1 text-[11px] font-semibold text-[color:var(--color-ink)]">
          {pick(summary.clientName, language)}
        </dd>
      </div>
      <div>
        <dt className="text-[8px] font-bold uppercase tracking-[0.14em] text-[color:var(--color-muted)]">
          {copy.court}
        </dt>
        <dd className="mt-1 text-[11px] font-semibold text-[color:var(--color-ink)]">
          {pick(summary.court, language)}
        </dd>
      </div>
      <div>
        <dt className="text-[8px] font-bold uppercase tracking-[0.14em] text-[color:var(--color-muted)]">
          {copy.hearingDate}
        </dt>
        <dd className="mt-1 text-[11px] font-semibold text-[color:var(--color-ink)]">
          {hearingDateLabel(summary.hearingDate, language)}
        </dd>
      </div>
      <div>
        <dt className="text-[8px] font-bold uppercase tracking-[0.14em] text-[color:var(--color-muted)]">
          {copy.preparedBy}
        </dt>
        <dd className="mt-1 text-[11px] font-semibold text-[color:var(--color-ink)]">
          {pick(profile.name, language)}
        </dd>
      </div>
      <div>
        <dt className="text-[8px] font-bold uppercase tracking-[0.14em] text-[color:var(--color-muted)]">
          {copy.status}
        </dt>
        <dd className="mt-1 text-[11px] font-semibold text-[color:var(--color-ink)]">
          {dictionaries[language].caseDetail.summary[summary.status]}
        </dd>
      </div>
    </dl>
  );
}

function SummaryBody({
  sections,
  language,
  copy,
}: {
  sections: SummarySection[];
  language: Language;
  copy: Dictionary["hearingSummary"];
}) {
  return sections.map((section, index) => (
    <section key={section.id} className="mt-7">
      <div className="flex items-baseline gap-3 border-b border-[color:var(--color-border)] pb-2">
        <span className="font-serif text-[20px] leading-none text-[color:var(--color-green)]">
          {numberFor(language, index + 1)}.
        </span>
        <h2 className="m-0 text-[14px] font-bold text-[color:var(--color-ink)]">
          {copy.sections[section.id]}
        </h2>
      </div>
      <ol className="mt-3 grid gap-3">
        {section.claims.map((claim) => {
          const verified = claim.verification === "verified";

          return (
            <li
              key={claim.id}
              className="rounded-lg border border-[color:var(--color-border)] bg-[color:var(--color-surface)] px-4 py-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded-full px-2 py-0.5 text-[8px] font-bold ${claimTone[claim.type]}`}
                >
                  {copy.claimTypes[claim.type]}
                </span>
                <span
                  className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[8px] font-bold ${
                    verified
                      ? "bg-[#eaf6ef] text-[var(--color-deep)]"
                      : "border border-[#f0cfc6] bg-[#fdf3f0] text-[#8a2e1e]"
                  }`}
                >
                  {verified ? <Icon name="check" size={11} /> : null}
                  {verified ? copy.verified : copy.unverified}
                </span>
              </div>
              <p className="mt-2 text-[11px] leading-relaxed text-[color:var(--color-ink)]">
                {pick(claim.text, language)}
              </p>
              <p className="mt-2 flex items-start gap-1.5 text-[8px] leading-relaxed text-[color:var(--color-muted)]">
                <span className="mt-px shrink-0">
                  <Icon name="document" size={11} />
                </span>
                <span>
                  <b className="font-bold">{copy.source}:</b>{" "}
                  {pick(claim.source, language)}
                </span>
              </p>
              {verified ? null : (
                <p className="mt-1.5 text-[8px] font-semibold text-[#8a2e1e]">
                  {copy.unverifiedNote}
                </p>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  ));
}

function SummaryEditor({
  summary,
  caseId,
  hearingId,
  language,
  copy,
  path,
}: {
  summary: HearingSummary;
  caseId: string;
  hearingId: string;
  language: Language;
  copy: Dictionary["hearingSummary"];
  path: string;
}) {
  return (
    <form action={saveHearingSummaryAction} id="editor" className="mt-6">
      <input type="hidden" name="caseId" value={caseId} />
      <input type="hidden" name="hearingId" value={hearingId} />
      <input type="hidden" name="language" value={language} />

      <div className="rounded-lg border border-[#e8d9b5] bg-[#fbf6e9] px-4 py-3">
        <h2 className="m-0 text-[13px] font-bold text-[#6b5326]">
          {copy.edit}
        </h2>
        <p className="mt-1 text-[9px] leading-relaxed text-[#6b5326]">
          {copy.editHint}
        </p>
      </div>

      {summary.sections.map((section, index) => (
        <fieldset
          key={section.id}
          className="mt-5 rounded-lg border border-[color:var(--color-border)] bg-[color:var(--color-surface)] px-4 py-3"
        >
          <legend className="px-1 text-[11px] font-bold text-[color:var(--color-ink)]">
            {numberFor(language, index + 1)}. {copy.sections[section.id]}
          </legend>
          <div className="mt-2 grid gap-3">
            {section.claims.map((claim) => {
              const prefix = `claim:${section.id}:${claim.id}`;

              return (
                <div
                  key={claim.id}
                  className="rounded-md border border-[color:var(--color-border)] bg-[color:var(--color-surface)] px-3 py-3"
                >
                  <div className="grid gap-3 sm:grid-cols-2">
                    <label className="block">
                      <span className="field-label">{copy.editText}</span>
                      <textarea
                        name={`${prefix}:text`}
                        required
                        rows={3}
                        defaultValue={pick(claim.text, language)}
                        className={`${inputClass} min-h-[76px]`}
                      />
                    </label>
                    <label className="block">
                      <span className="field-label">{copy.editSource}</span>
                      <input
                        name={`${prefix}:source`}
                        required
                        defaultValue={pick(claim.source, language)}
                        className={`${inputClass} h-11`}
                      />
                    </label>
                  </div>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    <label className="block">
                      <span className="field-label">{copy.claimType}</span>
                      <select
                        name={`${prefix}:type`}
                        defaultValue={claim.type}
                        className={`${inputClass} h-11`}
                      >
                        {(
                          [
                            "document",
                            "lawyer",
                            "ai",
                            "assumption",
                          ] as ClaimType[]
                        ).map((type) => (
                          <option key={type} value={type}>
                            {copy.claimTypes[type]}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="block">
                      <span className="field-label">{copy.verification}</span>
                      <select
                        name={`${prefix}:verification`}
                        defaultValue={claim.verification}
                        className={`${inputClass} h-11`}
                      >
                        <option value="verified">{copy.verified}</option>
                        <option value="unverified">{copy.unverified}</option>
                      </select>
                    </label>
                  </div>
                </div>
              );
            })}
          </div>
        </fieldset>
      ))}

      <div className="mt-6 flex flex-wrap items-center justify-end gap-2">
        <Link className="ghost-button" href={path}>
          {copy.cancel}
        </Link>
        <button className="primary-button fit" type="submit">
          {copy.saveVersion}
        </button>
      </div>
    </form>
  );
}

export default async function HearingSummaryPage({
  params,
  searchParams,
}: {
  params: Promise<{ caseId: string; hearingId: string }>;
  searchParams: Promise<{
    edit?: string;
    saved?: string;
    approved?: string;
    download?: string;
    editError?: string;
    approveError?: string;
  }>;
}) {
  const { caseId, hearingId } = await params;
  const { edit, saved, approved, download, editError, approveError } =
    await searchParams;
  const language = await getLanguage();
  const copy = dictionaries[language].hearingSummary;
  const matter = getCase(caseId);
  const hearingExists = listHearings(caseId).some(
    (hearing) => hearing.id === hearingId,
  );

  if (!matter || !hearingExists) notFound();

  const summary = await getHearingSummary(caseId, hearingId);

  if (!summary) {
    return (
      <>
        <Link className="back-link" href={`/lawyer/matters/${caseId}`}>
          <Icon name="arrow" size={15} />
          {copy.back}
        </Link>
        <div className="panel empty-state">
          <Icon name="document" size={28} />
          <h1>{copy.unavailable}</h1>
          <p>{copy.unavailableBody}</p>
          <Link className="ghost-button" href={`/lawyer/matters/${caseId}`}>
            {copy.back}
          </Link>
        </div>
      </>
    );
  }

  const path = `/lawyer/matters/${caseId}/hearings/${hearingId}/summary`;
  const editing = edit === "1";
  const isApproved = summary.status === "approved";

  return (
    <>
      <Link className="back-link" href={`/lawyer/matters/${caseId}`}>
        <Icon name="arrow" size={15} />
        {copy.back}
      </Link>

      <article className="panel mx-auto max-w-[840px] p-6 sm:p-10">
        <header className="border-b-2 border-[color:var(--color-ink)] pb-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-[9px] font-bold uppercase tracking-[0.2em] text-[color:var(--color-green)]">
              {copy.eyebrow}
            </span>
            <span
              className={`rounded-full border px-2.5 py-1 text-[8px] font-bold uppercase tracking-[0.1em] ${
                isApproved
                  ? "border-[#bfe3cd] bg-[#eaf6ef] text-[var(--color-deep)]"
                  : "border-[#f0cfc6] bg-[#fdf3f0] text-[#8a2e1e]"
              }`}
            >
              {isApproved ? copy.approvedBadge : copy.draft}
            </span>
          </div>
          <p className="mt-6 text-[9px] font-bold uppercase tracking-[0.3em] text-[color:var(--color-muted)]">
            {copy.memoHeading}
          </p>
          <h1 className="mt-2 font-serif text-[34px] leading-none text-[color:var(--color-ink)]">
            {format(copy.title, {
              number: numberFor(language, summary.hearingNumber),
            })}
          </h1>
          <p className="mt-3 text-[11px] text-[color:var(--color-muted)]">
            {pick(summary.matterTitle, language)} · {summary.caseId}
          </p>
        </header>

        <MemoHeader summary={summary} language={language} copy={copy} />

        <div
          id="share"
          className="mt-5 flex flex-wrap items-center gap-2 border-b border-[color:var(--color-border)] pb-5"
        >
          {editing ? (
            <Link className="ghost-button" href={path}>
              {copy.cancel}
            </Link>
          ) : (
            <>
              <Link
                className="outline-button small"
                href={`${path}?edit=1#editor`}
              >
                <Icon name="document" size={14} />
                {copy.edit}
              </Link>
              {isApproved ? null : (
                <form action={approveHearingSummaryAction}>
                  <input type="hidden" name="caseId" value={caseId} />
                  <input type="hidden" name="hearingId" value={hearingId} />
                  <button className="primary-button fit" type="submit">
                    {copy.approve}
                  </button>
                </form>
              )}
              <form action={downloadHearingSummaryAction} id="download">
                <input type="hidden" name="caseId" value={caseId} />
                <input type="hidden" name="hearingId" value={hearingId} />
                <button className="outline-button small" type="submit">
                  <Icon name="download" size={14} />
                  {copy.download}
                </button>
              </form>
            </>
          )}
        </div>

        {editError ? (
          <p className="form-error mt-4" role="alert">
            {copy.saveError}
          </p>
        ) : null}
        {approveError ? (
          <p className="form-error mt-4" role="alert">
            {copy.approveError}
          </p>
        ) : null}
        {saved && !editError ? (
          <p
            className="mt-4 rounded-md border border-[#bfe3cd] bg-[#eaf6ef] px-3 py-2 text-[9px] font-semibold text-[var(--color-deep)]"
            role="status"
          >
            {format(copy.savedNotice, {
              number: numberFor(language, summary.version),
            })}
          </p>
        ) : null}
        {approved && !approveError ? (
          <p
            className="mt-4 rounded-md border border-[#bfe3cd] bg-[#eaf6ef] px-3 py-2 text-[9px] font-semibold text-[var(--color-deep)]"
            role="status"
          >
            {copy.approvedNotice}
          </p>
        ) : null}
        {download === "NOT_CONFIGURED" ? (
          <p
            className="mt-4 rounded-md border border-dashed border-[color:var(--color-border)] bg-[color:var(--color-surface)] px-3 py-2 text-[9px] font-semibold text-[color:var(--color-muted)]"
            role="status"
          >
            {copy.downloadNotConfigured}
          </p>
        ) : null}

        <aside className="mt-5 rounded-lg border border-[#e8d9b5] bg-[#fbf6e9] px-4 py-3">
          <p className="text-[10px] leading-relaxed text-[#6b5326]">
            {copy.notLegalAdvice}
          </p>
        </aside>

        <p className="mt-4 rounded-md border border-dashed border-[color:var(--color-border)] bg-[color:var(--color-surface)] px-3 py-2 text-[9px] leading-relaxed text-[color:var(--color-muted)]">
          {copy.mock}
        </p>

        {editing ? (
          <SummaryEditor
            summary={summary}
            caseId={caseId}
            hearingId={hearingId}
            language={language}
            copy={copy}
            path={path}
          />
        ) : (
          <SummaryBody
            sections={summary.sections}
            language={language}
            copy={copy}
          />
        )}

        <section
          id="versions"
          className="mt-8 border-t border-[color:var(--color-border)] pt-5"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="m-0 text-[14px] font-bold text-[color:var(--color-ink)]">
              {copy.versionHistory}
            </h2>
            <span className="count-chip">
              {format(copy.versionsCount, {
                count: numberFor(language, summary.versions.length),
              })}
            </span>
          </div>
          <ol className="mt-3 grid gap-2">
            {summary.versions.map((version, index) => {
              const current = index === summary.versions.length - 1;

              return (
                <li
                  key={version.id}
                  className="rounded-lg border border-[color:var(--color-border)] bg-[color:var(--color-surface)] px-4 py-3"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <b className="text-[10px] text-[color:var(--color-ink)]">
                      {format(copy.versionLabel, {
                        number: numberFor(language, version.version),
                      })}
                    </b>
                    {current ? (
                      <span className="rounded-full bg-[#eaf6ef] px-2 py-0.5 text-[8px] font-bold text-[var(--color-deep)]">
                        {copy.currentVersion}
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 text-[8px] leading-relaxed text-[color:var(--color-muted)]">
                    {format(copy.versionMeta, {
                      date: versionDateLabel(version.createdAt, language),
                      name: pick(version.editedBy, language),
                    })}
                  </p>
                </li>
              );
            })}
          </ol>
        </section>

        <footer className="mt-8 border-t border-[color:var(--color-border)] pt-4 text-[8px] leading-relaxed text-[color:var(--color-muted)]">
          {copy.notLegalAdvice}
        </footer>
      </article>
    </>
  );
}
