import type { Metadata } from "next";
import Link from "next/link";
import { signOut, signOutAll } from "@/app/actions";
import { Icon } from "@/components/Icon";
import { LanguageToggle } from "@/components/LanguageToggle";
import { PageHeading } from "@/components/lawyer/PageHeading";
import { PhotoPanel } from "@/components/lawyer/PhotoPanel";
import { ProfileDetails } from "@/components/lawyer/ProfileDetails";
import { ProfileForm } from "@/components/lawyer/ProfileForm";
import { getLawyerProfile, getLawyerProfileDetail } from "@/lib/api/lawyer";
import { dictionaries, pick, titleFor } from "@/lib/i18n";
import { getLanguage } from "@/lib/language";
import { usedDemoData } from "@/lib/api/backendClient";

export async function generateMetadata(): Promise<Metadata> {
  const language = await getLanguage();
  return { title: titleFor(language, "lawyerSettings") };
}

export default async function SettingsPage({
  searchParams,
}: {
  searchParams: Promise<{ edit?: string; profile?: string; photo?: string }>;
}) {
  const { edit, profile: profileResult, photo: photoResult } = await searchParams;
  const language = await getLanguage();
  const copy = dictionaries[language];
  const settings = copy.settings;
  const profileCopy = copy.lawyerProfile;
  const [profile, detail] = await Promise.all([getLawyerProfile(), getLawyerProfileDetail()]);
  const editing = edit === "1" && detail !== null;

  return (
    <>
      <PageHeading
        eyebrow={settings.eyebrow}
        title={settings.title}
        subtitle={settings.subtitle}
      />
      {usedDemoData() ? <p className="mock-note">{copy.common.mockData}</p> : null}

      <div className="settings-grid">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>{settings.languageTitle}</h2>
              <p>{settings.languageBody}</p>
            </div>
          </div>
          <div className="settings-language">
            <LanguageToggle language={language} compact />
          </div>
        </section>

        {detail ? (
          <PhotoPanel name={detail.fullName} photoId={detail.photoId} result={photoResult} copy={profileCopy} />
        ) : null}

        <section className="panel" id="profile">
          <div className="panel-head">
            <div>
              <h2>{settings.profileTitle}</h2>
              <p>{settings.profileBody}</p>
            </div>
            {detail && !editing ? (
              <Link className="outline-button small" href="/lawyer/settings?edit=1#profile">
                {settings.editProfile}
              </Link>
            ) : null}
          </div>
          {profileResult === "saved" ? (
            <p className="success-note" role="status">
              {settings.profileSaved}
            </p>
          ) : null}
          {editing && detail ? (
            <ProfileForm
              detail={detail}
              copy={settings}
              profileCopy={profileCopy}
              error={profileResult !== undefined && profileResult !== "saved"}
            />
          ) : (
          <dl className="profile-list">
            <div>
              <dt>{settings.name}</dt>
              <dd>{pick(profile.name, language)}</dd>
            </div>
            <div>
              <dt>{settings.role}</dt>
              <dd>{settings.roleValue}</dd>
            </div>
            <div>
              <dt>{settings.firm}</dt>
              <dd>{pick(profile.firm, language)}</dd>
            </div>
            <div>
              <dt>{settings.email}</dt>
              <dd>{profile.email}</dd>
            </div>
            {detail?.phone ? (
              <div>
                <dt>{settings.phone}</dt>
                <dd>{detail.phone}</dd>
              </div>
            ) : null}
            <div>
              <dt>{settings.location}</dt>
              <dd>{pick(profile.location, language)}</dd>
            </div>
            {detail ? <ProfileDetails details={detail} copy={profileCopy} language={language} /> : null}
          </dl>
          )}
        </section>

        <section className="panel settings-signout">
          <div className="panel-head">
            <div>
              <h2>{settings.signOutTitle}</h2>
              <p>{settings.signOutBody}</p>
            </div>
            <form action={signOut}>
              <button className="outline-button" type="submit">
                <Icon name="logout" size={17} />
                {settings.signOut}
              </button>
            </form>
          </div>
        </section>

        <section className="panel settings-signout">
          <div className="panel-head">
            <div>
              <h2>{settings.signOutAll}</h2>
              <p>{settings.signOutAllBody}</p>
            </div>
            <form action={signOutAll}>
              <button className="outline-button" type="submit">
                <Icon name="logout" size={17} />
                {settings.signOutAll}
              </button>
            </form>
          </div>
        </section>
      </div>
    </>
  );
}
