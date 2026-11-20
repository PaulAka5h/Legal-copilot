import type { Metadata } from "next";
import { signOut, signOutAll } from "@/app/actions";
import { Icon } from "@/components/Icon";
import { LanguageToggle } from "@/components/LanguageToggle";
import { PageHeading } from "@/components/lawyer/PageHeading";
import { getLawyerProfile } from "@/lib/api/lawyer";
import { dictionaries, pick, titleFor } from "@/lib/i18n";
import { getLanguage } from "@/lib/language";

export async function generateMetadata(): Promise<Metadata> {
  const language = await getLanguage();
  return { title: titleFor(language, "lawyerSettings") };
}

export default async function SettingsPage() {
  const language = await getLanguage();
  const copy = dictionaries[language];
  const settings = copy.settings;
  const profile = getLawyerProfile();

  return (
    <>
      <PageHeading
        eyebrow={settings.eyebrow}
        title={settings.title}
        subtitle={settings.subtitle}
      />
      <p className="mock-note">{copy.common.mockData}</p>

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

        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>{settings.profileTitle}</h2>
              <p>{settings.profileBody}</p>
            </div>
          </div>
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
            <div>
              <dt>{settings.location}</dt>
              <dd>{pick(profile.location, language)}</dd>
            </div>
          </dl>
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
