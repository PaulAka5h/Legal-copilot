import type { Metadata } from "next";
import Link from "next/link";
import { Icon, type IconName } from "@/components/Icon";
import { PageHeading } from "@/components/lawyer/PageHeading";
import { QuickActions } from "@/components/lawyer/QuickActions";
import {
  getLawyerProfile,
  getLawyerStats,
  getRecentActivity,
  getRecentMatters,
} from "@/lib/api/lawyer";
import {
  dictionaries,
  format,
  numberFor,
  pick,
  titleFor,
} from "@/lib/i18n";
import { getLanguage } from "@/lib/language";

export async function generateMetadata(): Promise<Metadata> {
  const language = await getLanguage();
  return { title: titleFor(language, "lawyerDashboard") };
}

function Stat({
  icon,
  value,
  label,
  trend,
  tone,
}: {
  icon: IconName;
  value: string;
  label: string;
  trend: string;
  tone: "green" | "blue" | "cream";
}) {
  return (
    <div className="stat-card">
      <div className={`stat-icon ${tone === "green" ? "" : tone}`}>
        <Icon name={icon} />
      </div>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      <div className="stat-trend">{trend}</div>
    </div>
  );
}

export default async function LawyerDashboardPage() {
  const language = await getLanguage();
  const copy = dictionaries[language];
  const dashboard = copy.dashboard;
  const profile = getLawyerProfile();
  const stats = getLawyerStats();
  const recentMatters = getRecentMatters();
  const activities = getRecentActivity();

  const nextValue = stats.nextHearing
    ? `${numberFor(language, stats.nextHearing.day)} ${pick(stats.nextHearing.month, language)}`
    : "—";
  const nextTrend = stats.nextHearing
    ? pick(stats.nextHearing.matterTitle, language)
    : dashboard.statNone;

  return (
    <>
      <PageHeading
        eyebrow={dashboard.eyebrow}
        title={format(dashboard.greeting, {
          name: pick(profile.firstName, language),
        })}
        subtitle={dashboard.subtitle}
        action={
          <Link className="outline-button" href="/lawyer/matters">
            {dashboard.viewAll}
            <Icon name="arrow" size={17} />
          </Link>
        }
      />

      <p className="mock-note">{copy.common.mockData}</p>

      <div className="stats-grid">
        <Stat
          icon="briefcase"
          value={numberFor(language, stats.activeCases)}
          label={dashboard.statActive}
          trend={format(dashboard.statActiveTrend, {
            active: numberFor(language, stats.activeCases),
            total: numberFor(language, stats.totalMatters),
          })}
          tone="green"
        />
        <Stat
          icon="clients"
          value={numberFor(language, stats.totalClients)}
          label={dashboard.statClients}
          trend={format(dashboard.statClientsTrend, {
            count: numberFor(language, stats.totalClients),
          })}
          tone="blue"
        />
        <Stat
          icon="calendar"
          value={nextValue}
          label={dashboard.statHearing}
          trend={nextTrend}
          tone="cream"
        />
      </div>

      <section className="dashboard-grid">
        <div className="panel">
          <div className="panel-head">
            <div>
              <h2>{dashboard.recentMatters}</h2>
              <p>{dashboard.recentMattersSub}</p>
            </div>
            <Link className="text-link" href="/lawyer/matters">
              {dashboard.seeAll}
            </Link>
          </div>
          <div className="hearing-list">
            {recentMatters.map((matter, index) => (
              <Link className="hearing-row" key={matter.id} href="/lawyer/matters">
                <span className={`date-box d${index}`}>
                  <b>
                    {matter.nextHearing
                      ? numberFor(language, matter.nextHearing.day)
                      : "—"}
                  </b>
                  <small>
                    {matter.nextHearing
                      ? pick(matter.nextHearing.month, language)
                      : ""}
                  </small>
                </span>
                <span className="hearing-info">
                  <b>{pick(matter.title, language)}</b>
                  <small>
                    {matter.nextHearing
                      ? `${pick(matter.nextHearing.time, language)} · ${pick(matter.court, language)}`
                      : pick(matter.court, language)}
                  </small>
                </span>
                <Icon name="chevron" size={18} />
              </Link>
            ))}
          </div>
        </div>

        <div className="panel activity-panel">
          <div className="panel-head">
            <div>
              <h2>{dashboard.recentActivity}</h2>
              <p>{dashboard.recentActivitySub}</p>
            </div>
          </div>
          <div className="activity-list">
            {activities.map((activity) => (
              <div className="activity-item" key={activity.id}>
                <span>
                  <Icon name={activity.icon} size={18} />
                </span>
                <div>
                  <b>{pick(activity.title, language)}</b>
                  <p>{pick(activity.detail, language)}</p>
                  <small>{pick(activity.time, language)}</small>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <QuickActions language={language} />
    </>
  );
}
