import { createContext, FormEvent, ReactNode, useContext, useEffect, useState } from "react";

type Language = "en" | "bn";

const LanguageContext = createContext<{
  language: Language;
  setLanguage: (language: Language) => void;
}>({ language: "en", setLanguage: () => undefined });

function useLanguage() {
  return useContext(LanguageContext);
}

type Screen =
  | "lawyer-login"
  | "dashboard"
  | "matters"
  | "new-client"
  | "client-login"
  | "client-dashboard"
  | "case-detail";

type IconName =
  | "arrow"
  | "briefcase"
  | "calendar"
  | "check"
  | "chevron"
  | "clients"
  | "close"
  | "copy"
  | "dashboard"
  | "document"
  | "download"
  | "eye"
  | "lock"
  | "logout"
  | "mail"
  | "menu"
  | "plus"
  | "search"
  | "user";

const paths: Record<IconName, ReactNode> = {
  arrow: (
    <>
      <path d="M5 12h14" />
      <path d="m13 6 6 6-6 6" />
    </>
  ),
  briefcase: (
    <>
      <rect x="3" y="7" width="18" height="13" rx="2" />
      <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18M10 12v2h4v-2" />
    </>
  ),
  calendar: (
    <>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M16 3v4M8 3v4M3 10h18" />
    </>
  ),
  check: <path d="m5 12 4 4L19 6" />,
  chevron: <path d="m9 18 6-6-6-6" />,
  clients: (
    <>
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
    </>
  ),
  close: (
    <>
      <path d="m6 6 12 12M18 6 6 18" />
    </>
  ),
  copy: (
    <>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M15 9V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h3" />
    </>
  ),
  dashboard: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </>
  ),
  document: (
    <>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
      <path d="M14 2v6h6M8 13h8M8 17h6" />
    </>
  ),
  download: (
    <>
      <path d="M12 3v12m0 0 5-5m-5 5-5-5M5 21h14" />
    </>
  ),
  eye: (
    <>
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  lock: (
    <>
      <rect x="4" y="10" width="16" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
    </>
  ),
  logout: (
    <>
      <path d="M10 17l5-5-5-5M15 12H3M21 19V5a2 2 0 0 0-2-2h-6" />
    </>
  ),
  mail: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3 7 9 6 9-6" />
    </>
  ),
  menu: (
    <>
      <path d="M4 7h16M4 12h16M4 17h16" />
    </>
  ),
  plus: (
    <>
      <path d="M12 5v14M5 12h14" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-4-4" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0 1 16 0" />
    </>
  ),
};

function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}

function Logo({ light = false }: { light?: boolean }) {
  return (
    <button
      className={`logo ${light ? "logo-light" : ""}`}
      onClick={() => undefined}
      aria-label="Legal Copilot"
    >
      <span className="logo-mark">
        <span>LC</span>
      </span>
      <span className="logo-copy">
        <b>Legal Copilot</b>
        <small>
          <Bilingual en="Legal workspace" bn="আইনি সহায়ক" />
        </small>
      </span>
    </button>
  );
}

function Bilingual({ en, bn }: { en: string; bn: string }) {
  const { language } = useLanguage();
  return <>{language === "en" ? en : bn}</>;
}

function LanguageToggle({ compact = false }: { compact?: boolean }) {
  const { language, setLanguage } = useLanguage();
  return (
    <div className={`language-pill ${compact ? "compact" : ""}`}>
      <button className={language === "en" ? "active" : ""} onClick={() => setLanguage("en")}>
        EN
      </button>
      <span aria-hidden="true">|</span>
      <button className={language === "bn" ? "active" : ""} onClick={() => setLanguage("bn")}>
        বাংলা
      </button>
    </div>
  );
}

const cases = [
  {
    id: "LC-24018",
    title: "Rahman vs. Karim",
    bn: "রহমান বনাম করিম",
    client: "Fahim Rahman",
    clientBn: "ফাহিম রহমান",
    court: "Dhaka District Court",
    courtBn: "ঢাকা জেলা আদালত",
    hearing: "3",
    status: "In progress",
    statusBn: "চলমান",
  },
  {
    id: "LC-24012",
    title: "Ahmed Property Matter",
    bn: "আহমেদ সম্পত্তি বিষয়ক",
    client: "Nusrat Ahmed",
    clientBn: "নুসরাত আহমেদ",
    court: "High Court Division",
    courtBn: "হাইকোর্ট বিভাগ",
    hearing: "2",
    status: "Next hearing",
    statusBn: "পরবর্তী শুনানি",
  },
  {
    id: "LC-23997",
    title: "Khan & Co. Agreement",
    bn: "খান অ্যান্ড কোং চুক্তি",
    client: "Rafiq Khan",
    clientBn: "রফিক খান",
    court: "Arbitration Tribunal",
    courtBn: "সালিশি ট্রাইব্যুনাল",
    hearing: "5",
    status: "Awaiting order",
    statusBn: "আদেশের অপেক্ষায়",
  },
  {
    id: "LC-23986",
    title: "Sultana Family Matter",
    bn: "সুলতানা পারিবারিক বিষয়",
    client: "Samira Sultana",
    clientBn: "সামিরা সুলতানা",
    court: "Family Court, Dhaka",
    courtBn: "পারিবারিক আদালত, ঢাকা",
    hearing: "4",
    status: "In progress",
    statusBn: "চলমান",
  },
];

const screenNames: Record<Screen, string> = {
  "lawyer-login": "Lawyer Login",
  dashboard: "Lawyer Dashboard",
  matters: "My Matters",
  "new-client": "New Client",
  "client-login": "Client Login",
  "client-dashboard": "Client Dashboard",
  "case-detail": "Case Detail",
};

export default function App() {
  const [language, setLanguage] = useState<Language>("en");

  return (
    <LanguageContext.Provider value={{ language, setLanguage }}>
      <AppContent />
    </LanguageContext.Provider>
  );
}

function AppContent() {
  const { language } = useLanguage();
  const [screen, setScreen] = useState<Screen>("lawyer-login");
  const [menuOpen, setMenuOpen] = useState(false);
  const [quickOpen, setQuickOpen] = useState(false);
  const [toast, setToast] = useState("");

  const navigate = (next: Screen) => {
    setScreen(next);
    setMenuOpen(false);
    setQuickOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const notify = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 2200);
  };

  useEffect(() => {
    document.title = `${screenNames[screen]} - ${language === "en" ? "EN" : "BN"} | Legal Copilot`;
  }, [language, screen]);

  if (screen === "lawyer-login")
    return (
      <LawyerLogin
        onLogin={() => navigate("dashboard")}
        onClient={() => navigate("client-login")}
      />
    );
  if (screen === "client-login")
    return (
      <ClientLogin
        onLogin={() => navigate("client-dashboard")}
        onLawyer={() => navigate("lawyer-login")}
      />
    );

  const isClient = screen === "client-dashboard";

  return (
    <div
      className={`app-shell language-${language}`}
      lang={language}
      data-frame-name={`${screenNames[screen]} - ${language === "en" ? "EN" : "BN"}`}
    >
      {!isClient && (
        <Sidebar
          screen={screen}
          onNavigate={navigate}
          open={menuOpen}
          onClose={() => setMenuOpen(false)}
        />
      )}
      <div className={isClient ? "client-shell" : "workspace"}>
        <Topbar
          isClient={isClient}
          onMenu={() => setMenuOpen(true)}
          onLogout={() => navigate(isClient ? "client-login" : "lawyer-login")}
        />
        <main className="main-content">
          {screen === "dashboard" && <Dashboard onNavigate={navigate} />}
          {screen === "matters" && <Matters onOpen={() => navigate("case-detail")} />}
          {screen === "new-client" && (
            <NewClient
              onDone={() =>
                notify(
                  language === "en" ? "Client created successfully" : "মক্কেল সফলভাবে তৈরি হয়েছে",
                )
              }
            />
          )}
          {screen === "client-dashboard" && <ClientDashboard notify={notify} />}
          {screen === "case-detail" && (
            <CaseDetail notify={notify} onBack={() => navigate("matters")} />
          )}
        </main>
        {!isClient && (
          <div className="quick-wrap">
            {quickOpen && (
              <div className="quick-menu">
                <button onClick={() => navigate("case-detail")}>
                  <span>
                    <Icon name="briefcase" size={18} />
                  </span>
                  <Bilingual en="New Case" bn="নতুন মামলা" />
                </button>
                <button onClick={() => navigate("new-client")}>
                  <span>
                    <Icon name="user" size={18} />
                  </span>
                  <Bilingual en="New Client" bn="নতুন মক্কেল" />
                </button>
              </div>
            )}
            <button
              className={`quick-button ${quickOpen ? "is-open" : ""}`}
              onClick={() => setQuickOpen(!quickOpen)}
              aria-label="Quick actions"
            >
              <Icon name="plus" size={25} />
            </button>
          </div>
        )}
      </div>
      {toast && (
        <div className="toast">
          <Icon name="check" size={18} /> {toast}
        </div>
      )}
    </div>
  );
}

function AuthLayout({
  type,
  children,
  switcher,
}: {
  type: "lawyer" | "client";
  children: ReactNode;
  switcher: ReactNode;
}) {
  const { language } = useLanguage();
  return (
    <div
      className={`auth-page language-${language}`}
      lang={language}
      data-frame-name={`${type === "lawyer" ? "Lawyer Login" : "Client Login"} - ${language === "en" ? "EN" : "BN"}`}
    >
      <aside className="auth-brand">
        <Logo light />
        <div className="brand-message">
          <span className="eyebrow light">
            <Bilingual en="Built for Bangladesh" bn="বাংলাদেশের জন্য তৈরি" />
          </span>
          <h1>
            {type === "lawyer" ? (
              <Bilingual en="Practice law." bn="সহজে মামলা পরিচালনা করুন।" />
            ) : (
              <Bilingual en="Your case," bn="আপনার মামলা," />
            )}
            <br />
            {type === "lawyer" ? (
              <Bilingual en="Not paperwork." bn="কাগজপত্র নয়।" />
            ) : (
              <Bilingual en="clearly explained." bn="সহজভাবে বুঝুন।" />
            )}
          </h1>
          <p>
            {type === "lawyer" ? (
              <Bilingual
                en="One calm, secure workspace for every matter, client and hearing."
                bn="প্রতিটি মামলা, মক্কেল ও শুনানির জন্য একটি নিরাপদ কর্মক্ষেত্র।"
              />
            ) : (
              <Bilingual
                en="Follow your matter, hearing dates and documents in one secure place."
                bn="এক নিরাপদ স্থানে আপনার মামলা, শুনানির তারিখ ও নথি দেখুন।"
              />
            )}
          </p>
        </div>
        <div className="trust-note">
          <Icon name="lock" size={17} />
          <Bilingual en="Private & secure" bn="ব্যক্তিগত ও নিরাপদ" />
        </div>
      </aside>
      <section className="auth-form-side">
        <div className="mobile-auth-logo">
          <Logo />
        </div>
        <LanguageToggle />
        <div className="auth-card">
          {children}
          <div className="auth-switch">{switcher}</div>
        </div>
      </section>
    </div>
  );
}

function LawyerLogin({ onLogin, onClient }: { onLogin: () => void; onClient: () => void }) {
  const [visible, setVisible] = useState(false);
  return (
    <AuthLayout
      type="lawyer"
      switcher={
        <>
          <button onClick={onClient}>
            <Bilingual en="Log in as a client" bn="মক্কেল হিসেবে লগ ইন করুন" />
          </button>
        </>
      }
    >
      <span className="eyebrow">
        <Bilingual en="Lawyer portal" bn="আইনজীবী পোর্টাল" />
      </span>
      <h2>
        <Bilingual en="Welcome back" bn="স্বাগতম" />
      </h2>
      <p className="form-intro">
        <Bilingual en="Sign in to manage your practice." bn="আপনার কাজ পরিচালনা করতে সাইন ইন করুন।" />
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onLogin();
        }}
      >
        <Field label={<Bilingual en="Email address" bn="ইমেইল ঠিকানা" />} icon="mail">
          <input type="email" defaultValue="farhana@rahmanlaw.bd" aria-label="Email address" />
        </Field>
        <Field
          label={<Bilingual en="Password" bn="পাসওয়ার্ড" />}
          icon="lock"
          action={
            <button type="button" className="field-action" onClick={() => setVisible(!visible)}>
              <Icon name="eye" size={18} />
            </button>
          }
        >
          <input
            type={visible ? "text" : "password"}
            defaultValue="legalcopilot"
            aria-label="Password"
          />
        </Field>
        <div className="form-row">
          <label className="check-label">
            <input type="checkbox" defaultChecked />
            <span>
              <Icon name="check" size={13} />
            </span>
            <Bilingual en="Remember me" bn="মনে রাখুন" />
          </label>
          <button type="button" className="text-link">
            <Bilingual en="Forgot password?" bn="পাসওয়ার্ড ভুলে গেছেন?" />
          </button>
        </div>
        <button className="primary-button" type="submit">
          <Bilingual en="Sign in" bn="সাইন ইন" />
          <Icon name="arrow" size={19} />
        </button>
      </form>
    </AuthLayout>
  );
}

function ClientLogin({ onLogin, onLawyer }: { onLogin: () => void; onLawyer: () => void }) {
  return (
    <AuthLayout
      type="client"
      switcher={
        <>
          <button onClick={onLawyer}>
            <Bilingual en="Log in as a lawyer" bn="আইনজীবী হিসেবে লগ ইন করুন" />
          </button>
        </>
      }
    >
      <span className="eyebrow">
        <Bilingual en="Client portal" bn="মক্কেল পোর্টাল" />
      </span>
      <h2>
        <Bilingual en="View your case" bn="আপনার মামলা দেখুন" />
      </h2>
      <p className="form-intro">
        <Bilingual en="Use the details shared by your lawyer." bn="আইনজীবীর দেওয়া তথ্য ব্যবহার করুন।" />
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onLogin();
        }}
      >
        <Field label={<Bilingual en="Client ID" bn="মক্কেল আইডি" />} icon="user">
          <input defaultValue="CL-7842-BD" aria-label="Client ID" />
        </Field>
        <Field label={<Bilingual en="Password" bn="পাসওয়ার্ড" />} icon="lock">
          <input type="password" defaultValue="J7q9fL2x" aria-label="Password" />
        </Field>
        <button className="primary-button" type="submit">
          <Bilingual en="View my case" bn="আমার মামলা দেখুন" />
          <Icon name="arrow" size={19} />
        </button>
      </form>
      <div className="help-note">
        <Icon name="lock" size={17} />
        <span>
          <Bilingual en="Your access is private." bn="আপনার প্রবেশাধিকার ব্যক্তিগত।" />
          <small>
            <Bilingual
              en="Contact your lawyer if you need new login details."
              bn="নতুন তথ্যের জন্য আইনজীবীর সাথে যোগাযোগ করুন।"
            />
          </small>
        </span>
      </div>
    </AuthLayout>
  );
}

function Field({
  label,
  icon,
  children,
  action,
}: {
  label: ReactNode;
  icon?: IconName;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      <span className="input-wrap">
        {icon && <Icon name={icon} size={18} />}
        {children}
        {action}
      </span>
    </label>
  );
}

function Sidebar({
  screen,
  onNavigate,
  open,
  onClose,
}: {
  screen: Screen;
  onNavigate: (s: Screen) => void;
  open: boolean;
  onClose: () => void;
}) {
  const items: { id: Screen; icon: IconName; en: string; bn: string }[] = [
    { id: "dashboard", icon: "dashboard", en: "Dashboard", bn: "ড্যাশবোর্ড" },
    { id: "matters", icon: "briefcase", en: "My Matters", bn: "আমার মামলা" },
    { id: "new-client", icon: "clients", en: "Clients", bn: "মক্কেল" },
  ];
  return (
    <>
      <div className={`drawer-backdrop ${open ? "show" : ""}`} onClick={onClose} />
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="sidebar-head">
          <Logo />
          <button className="mobile-close" onClick={onClose}>
            <Icon name="close" />
          </button>
        </div>
        <div className="side-section-label">
          <Bilingual en="Workspace" bn="কর্মক্ষেত্র" />
        </div>
        <nav>
          {items.map((item) => (
            <button
              key={item.id}
              className={screen === item.id ? "active" : ""}
              onClick={() => onNavigate(item.id)}
            >
              <Icon name={item.icon} size={19} />
              <Bilingual en={item.en} bn={item.bn} />
              {item.id === "matters" && <small>12</small>}
            </button>
          ))}
        </nav>
        <div className="sidebar-support">
          <div className="support-icon">
            <Icon name="document" size={19} />
          </div>
          <b>
            <Bilingual en="Need help?" bn="সাহায্য চান?" />
          </b>
          <p>
            <Bilingual en="Visit the practice guide." bn="প্র্যাকটিস গাইড দেখুন।" />
          </p>
          <button>
            <Bilingual en="Open guide" bn="গাইড খুলুন" /> <Icon name="arrow" size={15} />
          </button>
        </div>
        <div className="sidebar-footer">
          <span>
            <Bilingual en="Rahman & Associates" bn="রহমান অ্যান্ড অ্যাসোসিয়েটস" />
          </span>
          <small>
            <Bilingual en="Dhaka, Bangladesh" bn="ঢাকা, বাংলাদেশ" />
          </small>
        </div>
      </aside>
    </>
  );
}

function Topbar({
  isClient,
  onMenu,
  onLogout,
}: {
  isClient: boolean;
  onMenu: () => void;
  onLogout: () => void;
}) {
  return (
    <header className="topbar">
      <button className="menu-button" onClick={onMenu}>
        <Icon name="menu" />
        <span>
          <Bilingual en="Menu" bn="মেনু" />
        </span>
      </button>
      {isClient && <Logo />}
      <div className="topbar-right">
        <LanguageToggle compact />
        <div className="user-meta">
          <span className="avatar">{isClient ? "FR" : "FA"}</span>
          <span>
            <b>
              {isClient ? (
                <Bilingual en="Fahim Rahman" bn="ফাহিম রহমান" />
              ) : (
                <Bilingual en="Farhana Ahmed" bn="ফারহানা আহমেদ" />
              )}
            </b>
            <small>
              {isClient ? (
                <Bilingual en="Client" bn="মক্কেল" />
              ) : (
                <Bilingual en="Advocate" bn="আইনজীবী" />
              )}
            </small>
          </span>
        </div>
        <button className="icon-button" onClick={onLogout} aria-label="Log out">
          <Icon name="logout" size={19} />
        </button>
      </div>
    </header>
  );
}

function PageHeading({
  eyebrow,
  title,
  subtitle,
  action,
}: {
  eyebrow: ReactNode;
  title: ReactNode;
  subtitle: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      {action}
    </div>
  );
}

function Dashboard({ onNavigate }: { onNavigate: (s: Screen) => void }) {
  return (
    <>
      <PageHeading
        eyebrow={<Bilingual en="Tuesday, 14 January" bn="মঙ্গলবার, ১৪ জানুয়ারি" />}
        title={<Bilingual en="Good morning, Farhana" bn="সুপ্রভাত, ফারহানা" />}
        subtitle={
          <Bilingual
            en="Here is what needs your attention today."
            bn="আজ যে বিষয়গুলোতে আপনার মনোযোগ প্রয়োজন।"
          />
        }
        action={
          <button className="outline-button" onClick={() => onNavigate("matters")}>
            <Bilingual en="View all matters" bn="সব মামলা দেখুন" />
            <Icon name="arrow" size={17} />
          </button>
        }
      />
      <div className="stats-grid">
        <Stat
          icon="briefcase"
          value="12"
          en="Active cases"
          bn="সক্রিয় মামলা"
          trendEn="+2 this month"
          trendBn="এই মাসে +২"
          tone="green"
        />
        <Stat
          icon="clients"
          value="28"
          en="Total clients"
          bn="মোট মক্কেল"
          trendEn="+4 this month"
          trendBn="এই মাসে +৪"
          tone="blue"
        />
        <Stat
          icon="calendar"
          value={<Bilingual en="17 Jan" bn="১৭ জানু" />}
          en="Next hearing"
          bn="পরবর্তী শুনানি"
          trendEn="Rahman vs. Karim"
          trendBn="রহমান বনাম করিম"
          tone="cream"
        />
      </div>
      <section className="dashboard-grid">
        <div className="panel">
          <div className="panel-head">
            <div>
              <h2>
                <Bilingual en="Upcoming hearings" bn="আসন্ন শুনানি" />
              </h2>
              <p>
                <Bilingual en="Your next seven days" bn="আপনার আগামী সাত দিন" />
              </p>
            </div>
            <button className="text-link" onClick={() => onNavigate("matters")}>
              <Bilingual en="See calendar" bn="ক্যালেন্ডার দেখুন" />
            </button>
          </div>
          <div className="hearing-list">
            {[
              [
                "17",
                "JAN",
                "Rahman vs. Karim",
                "রহমান বনাম করিম",
                "10:30 AM · Dhaka District Court",
                "সকাল ১০:৩০ · ঢাকা জেলা আদালত",
              ],
              [
                "19",
                "JAN",
                "Ahmed Property Matter",
                "আহমেদ সম্পত্তি বিষয়ক",
                "12:00 PM · High Court Division",
                "দুপুর ১২:০০ · হাইকোর্ট বিভাগ",
              ],
              [
                "21",
                "JAN",
                "Khan & Co. Agreement",
                "খান অ্যান্ড কোং চুক্তি",
                "11:15 AM · Arbitration Tribunal",
                "সকাল ১১:১৫ · সালিশি ট্রাইব্যুনাল",
              ],
            ].map((h, i) => (
              <button className="hearing-row" key={h[0]} onClick={() => onNavigate("case-detail")}>
                <span className={`date-box d${i}`}>
                  <b>
                    <Bilingual en={h[0]} bn={["১৭", "১৯", "২১"][i]} />
                  </b>
                  <small>
                    <Bilingual en={h[1]} bn="জানু" />
                  </small>
                </span>
                <span className="hearing-info">
                  <b>
                    <Bilingual en={h[2]} bn={h[3]} />
                  </b>
                  <small>
                    <Bilingual en={h[4]} bn={h[5]} />
                  </small>
                </span>
                <Icon name="chevron" size={18} />
              </button>
            ))}
          </div>
        </div>
        <div className="panel activity-panel">
          <div className="panel-head">
            <div>
              <h2>
                <Bilingual en="Recent activity" bn="সাম্প্রতিক কার্যক্রম" />
              </h2>
              <p>
                <Bilingual en="Latest case updates" bn="সর্বশেষ মামলার আপডেট" />
              </p>
            </div>
          </div>
          <div className="activity-list">
            <Activity
              icon="document"
              title="Document added"
              bn="নথি যোগ হয়েছে"
              detail="Witness_Statement.pdf"
              detailBn="সাক্ষীর_বিবৃতি.pdf"
              time="18 min ago"
              timeBn="১৮ মিনিট আগে"
            />
            <Activity
              icon="calendar"
              title="Hearing rescheduled"
              bn="শুনানির সময় পরিবর্তন"
              detail="Ahmed Property Matter"
              detailBn="আহমেদ সম্পত্তি বিষয়ক"
              time="2 hours ago"
              timeBn="২ ঘণ্টা আগে"
            />
            <Activity
              icon="clients"
              title="New client created"
              bn="নতুন মক্কেল তৈরি"
              detail="Samira Sultana"
              detailBn="সামিরা সুলতানা"
              time="Yesterday"
              timeBn="গতকাল"
            />
          </div>
        </div>
      </section>
    </>
  );
}

function Stat({
  icon,
  value,
  en,
  bn,
  trendEn,
  trendBn,
  tone,
}: {
  icon: IconName;
  value: ReactNode;
  en: string;
  bn: string;
  trendEn: string;
  trendBn: string;
  tone: string;
}) {
  return (
    <div className="stat-card">
      <div className={`stat-icon ${tone}`}>
        <Icon name={icon} />
      </div>
      <div className="stat-value">{value}</div>
      <div className="stat-label">
        <Bilingual en={en} bn={bn} />
      </div>
      <div className="stat-trend">
        <Bilingual en={trendEn} bn={trendBn} />
      </div>
    </div>
  );
}

function Activity({
  icon,
  title,
  bn,
  detail,
  detailBn,
  time,
  timeBn,
}: {
  icon: IconName;
  title: string;
  bn: string;
  detail: string;
  detailBn: string;
  time: string;
  timeBn: string;
}) {
  return (
    <div className="activity-item">
      <span>
        <Icon name={icon} size={18} />
      </span>
      <div>
        <b>
          <Bilingual en={title} bn={bn} />
        </b>
        <p>
          <Bilingual en={detail} bn={detailBn} />
        </p>
        <small>
          <Bilingual en={time} bn={timeBn} />
        </small>
      </div>
    </div>
  );
}

function Matters({ onOpen }: { onOpen: () => void }) {
  const { language } = useLanguage();
  const [query, setQuery] = useState("");
  const filtered = cases.filter((item) =>
    `${item.title} ${item.client} ${item.court}`.toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <>
      <PageHeading
        eyebrow={<Bilingual en="Case management" bn="মামলা ব্যবস্থাপনা" />}
        title={<Bilingual en="My Matters" bn="আমার মামলা" />}
        subtitle={
          <Bilingual
            en="Track every case, hearing and client in one place."
            bn="প্রতিটি মামলা, শুনানি ও মক্কেল এক জায়গায় দেখুন।"
          />
        }
        action={
          <button className="primary-button fit">
            <Icon name="plus" size={18} />
            <Bilingual en="New case" bn="নতুন মামলা" />
          </button>
        }
      />
      <div className="panel matters-panel">
        <div className="table-tools">
          <label className="search-box">
            <Icon name="search" size={19} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={language === "en" ? "Search cases" : "মামলা খুঁজুন"}
            />
          </label>
          <div className="filter-pills">
            <button className="active">
              <Bilingual en="All" bn="সব" /> <span>12</span>
            </button>
            <button>
              <Bilingual en="Active" bn="সক্রিয়" /> <span>8</span>
            </button>
            <button>
              <Bilingual en="Closed" bn="নিষ্পত্তি" /> <span>4</span>
            </button>
          </div>
        </div>
        <div className="case-table">
          <div className="table-row table-header">
            <span>
              <Bilingual en="Matter" bn="মামলা" />
            </span>
            <span>
              <Bilingual en="Client" bn="মক্কেল" />
            </span>
            <span>
              <Bilingual en="Court" bn="আদালত" />
            </span>
            <span>
              <Bilingual en="Hearing" bn="শুনানি" />
            </span>
            <span>
              <Bilingual en="Status" bn="অবস্থা" />
            </span>
            <span />
          </div>
          {filtered.map((item) => (
            <button className="table-row" key={item.id} onClick={onOpen}>
              <span className="matter-cell">
                <small>{item.id}</small>
                <b>
                  <Bilingual en={item.title} bn={item.bn} />
                </b>
              </span>
              <span data-label={language === "en" ? "Client" : "মক্কেল"}>
                <Bilingual en={item.client} bn={item.clientBn} />
              </span>
              <span data-label={language === "en" ? "Court" : "আদালত"}>
                <Bilingual en={item.court} bn={item.courtBn} />
              </span>
              <span data-label={language === "en" ? "Hearing" : "শুনানি"}>
                <b className="hearing-number">#{item.hearing}</b>
              </span>
              <span data-label={language === "en" ? "Status" : "অবস্থা"}>
                <em className={`status status-${item.hearing}`}>
                  <span /> <Bilingual en={item.status} bn={item.statusBn} />
                </em>
              </span>
              <span>
                <Icon name="chevron" size={18} />
              </span>
            </button>
          ))}
          {!filtered.length && (
            <div className="empty-state">
              <Icon name="search" />
              <b>
                <Bilingual en="No matters found" bn="কোনো মামলা পাওয়া যায়নি" />
              </b>
            </div>
          )}
        </div>
        <div className="table-footer">
          <span>
            <Bilingual
              en={`Showing ${filtered.length} of 12 matters`}
              bn={`১২টির মধ্যে ${filtered.length}টি মামলা দেখানো হচ্ছে`}
            />
          </span>
          <div>
            <button disabled>‹</button>
            <button className="active">1</button>
            <button>2</button>
            <button>›</button>
          </div>
        </div>
      </div>
    </>
  );
}

function NewClient({ onDone }: { onDone: () => void }) {
  const { language } = useLanguage();
  const [saved, setSaved] = useState(false);
  const copy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      /* Preview clipboard permissions may vary. */
    }
    onDone();
  };
  if (saved)
    return (
      <div className="success-wrap">
        <div className="success-card">
          <span className="success-icon">
            <Icon name="check" size={30} />
          </span>
          <span className="eyebrow">
            <Bilingual en="Client created" bn="মক্কেল তৈরি হয়েছে" />
          </span>
          <h1>
            <Bilingual en="Nabila Chowdhury is ready" bn="নাবিলা চৌধুরী প্রস্তুত" />
          </h1>
          <p>
            <Bilingual
              en="Share these with your client."
              bn="এই তথ্যগুলো আপনার মক্কেলের সাথে শেয়ার করুন।"
            />
          </p>
          <div className="credentials">
            <div>
              <small>
                <Bilingual en="Client ID" bn="মক্কেল আইডি" />
              </small>
              <b>CL-7842-BD</b>
              <button onClick={() => copy("CL-7842-BD")}>
                <Icon name="copy" size={18} />
                <Bilingual en="Copy" bn="কপি" />
              </button>
            </div>
            <div>
              <small>
                <Bilingual en="Temporary password" bn="অস্থায়ী পাসওয়ার্ড" />
              </small>
              <b>J7q9fL2x</b>
              <button onClick={() => copy("J7q9fL2x")}>
                <Icon name="copy" size={18} />
                <Bilingual en="Copy" bn="কপি" />
              </button>
            </div>
          </div>
          <div className="security-callout">
            <Icon name="lock" size={18} />
            <Bilingual
              en="The client should change this password after first sign-in."
              bn="প্রথম সাইন ইন-এর পর মক্কেলকে পাসওয়ার্ড পরিবর্তন করতে হবে।"
            />
          </div>
          <button className="primary-button" onClick={() => setSaved(false)}>
            <Bilingual en="Add another client" bn="আরও মক্কেল যোগ করুন" />
            <Icon name="plus" size={18} />
          </button>
        </div>
      </div>
    );
  return (
    <>
      <PageHeading
        eyebrow={<Bilingual en="Client management" bn="মক্কেল ব্যবস্থাপনা" />}
        title={<Bilingual en="New Client" bn="নতুন মক্কেল" />}
        subtitle={
          <Bilingual
            en="Create secure portal access for your client."
            bn="মক্কেলের জন্য নিরাপদ পোর্টাল প্রবেশাধিকার তৈরি করুন।"
          />
        }
      />
      <form
        className="panel client-form"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          setSaved(true);
          onDone();
        }}
      >
        <div className="form-section-head">
          <span>01</span>
          <div>
            <h2>
              <Bilingual en="Personal details" bn="ব্যক্তিগত তথ্য" />
            </h2>
            <p>
              <Bilingual en="Enter the client's basic information." bn="মক্কেলের প্রাথমিক তথ্য লিখুন।" />
            </p>
          </div>
        </div>
        <div className="form-grid">
          <Field label={<Bilingual en="Full name" bn="পুরো নাম" />}>
            <input
              required
              placeholder={language === "en" ? "e.g. Nabila Chowdhury" : "যেমন নাবিলা চৌধুরী"}
            />
          </Field>
          <Field label={<Bilingual en="Mobile number" bn="মোবাইল নম্বর" />}>
            <input required placeholder="+880 1XXX XXXXXX" />
          </Field>
          <Field label={<Bilingual en="Email address" bn="ইমেইল ঠিকানা" />}>
            <input type="email" placeholder="client@example.com" />
          </Field>
          <Field label={<Bilingual en="National ID (optional)" bn="জাতীয় পরিচয়পত্র (ঐচ্ছিক)" />}>
            <input placeholder={language === "en" ? "NID number" : "এনআইডি নম্বর"} />
          </Field>
          <label className="field full">
            <span className="field-label">
              <Bilingual en="Address" bn="ঠিকানা" />
            </span>
            <textarea
              placeholder={
                language === "en" ? "House, road, area and district" : "বাড়ি, সড়ক, এলাকা ও জেলা"
              }
            />
          </label>
        </div>
        <div className="form-section-head second">
          <span>02</span>
          <div>
            <h2>
              <Bilingual en="Case assignment" bn="মামলা বরাদ্দ" />
            </h2>
            <p>
              <Bilingual en="You can update this later." bn="এটি পরে পরিবর্তন করা যাবে।" />
            </p>
          </div>
        </div>
        <div className="form-grid">
          <label className="field">
            <span className="field-label">
              <Bilingual en="Assign a matter" bn="মামলা বরাদ্দ করুন" />
            </span>
            <select defaultValue="">
              <option value="" disabled>
                {language === "en" ? "Select matter" : "মামলা নির্বাচন করুন"}
              </option>
              <option>{language === "en" ? "Rahman vs. Karim" : "রহমান বনাম করিম"}</option>
            </select>
          </label>
          <label className="field">
            <span className="field-label">
              <Bilingual en="Preferred language" bn="পছন্দের ভাষা" />
            </span>
            <select>
              <option>{language === "en" ? "Bangla" : "বাংলা"}</option>
              <option>{language === "en" ? "English" : "ইংরেজি"}</option>
            </select>
          </label>
        </div>
        <div className="form-actions">
          <button type="button" className="ghost-button">
            <Bilingual en="Cancel" bn="বাতিল" />
          </button>
          <button className="primary-button fit" type="submit">
            <Bilingual en="Save client" bn="মক্কেল সংরক্ষণ করুন" />
            <Icon name="arrow" size={18} />
          </button>
        </div>
      </form>
    </>
  );
}

const stages = [
  ["Case filed", "মামলা দায়ের", "12 Sep", "১২ সেপ্টেম্বর"],
  ["Notice served", "নোটিশ জারি", "28 Sep", "২৮ সেপ্টেম্বর"],
  ["Evidence", "সাক্ষ্য", "In progress", "চলমান"],
  ["Arguments", "যুক্তিতর্ক", "Upcoming", "আসন্ন"],
  ["Decision", "রায়", "Upcoming", "আসন্ন"],
];

function CaseProgress() {
  return (
    <div className="progress-wrap">
      <div className="progress-track">
        <span />
      </div>
      <div className="stage-list">
        {stages.map((stage, i) => (
          <div className={`stage ${i < 2 ? "complete" : i === 2 ? "current" : ""}`} key={stage[0]}>
            <span className="stage-dot">{i < 2 ? <Icon name="check" size={14} /> : i + 1}</span>
            <b>
              <Bilingual en={stage[0]} bn={stage[1]} />
            </b>
            <small>
              <Bilingual en={stage[2]} bn={stage[3]} />
            </small>
          </div>
        ))}
      </div>
    </div>
  );
}

const docs = [
  ["Petition_Copy.pdf", "আবেদনের কপি", "2.4 MB", "২.৪ এমবি", "12 Sep 2024", "১২ সেপ্টেম্বর ২০২৪"],
  ["Court_Order_02.pdf", "আদালতের আদেশ ০২", "1.1 MB", "১.১ এমবি", "21 Nov 2024", "২১ নভেম্বর ২০২৪"],
  ["Witness_Statement.pdf", "সাক্ষীর বিবৃতি", "3.8 MB", "৩.৮ এমবি", "10 Jan 2025", "১০ জানুয়ারি ২০২৫"],
];

function Documents({ notify }: { notify: (s: string) => void }) {
  const { language } = useLanguage();
  return (
    <div className="document-list">
      {docs.map((doc) => (
        <div className="document-row" key={doc[0]}>
          <span className="pdf-icon">
            <Bilingual en="PDF" bn="পিডিএফ" />
          </span>
          <span>
            <b>
              <Bilingual en={doc[0]} bn={doc[1]} />
            </b>
            <small>
              <Bilingual en={`${doc[2]} · ${doc[4]}`} bn={`${doc[3]} · ${doc[5]}`} />
            </small>
          </span>
          <button
            onClick={() => notify(language === "en" ? "Download started" : "ডাউনলোড শুরু হয়েছে")}
          >
            <Icon name="download" size={18} />
            <span>
              <Bilingual en="Download" bn="ডাউনলোড" />
            </span>
          </button>
        </div>
      ))}
    </div>
  );
}

function CaseHeader({ lawyer = false, onReview }: { lawyer?: boolean; onReview?: () => void }) {
  return (
    <div className="case-hero">
      <div>
        <span className="case-id">
          LC-24018{" "}
          <i>
            <Bilingual en="Active" bn="সক্রিয়" />
          </i>
        </span>
        <h1>
          <Bilingual en="Rahman vs. Karim" bn="রহমান বনাম করিম" />
        </h1>
        <p>
          <Icon name="briefcase" size={16} />
          <Bilingual en="Property dispute" bn="সম্পত্তি বিরোধ" /> <span>•</span>{" "}
          <Bilingual en="Dhaka District Court" bn="ঢাকা জেলা আদালত" />
        </p>
      </div>
      <div className="hearing-badge">
        <small>
          <Bilingual en="Current stage" bn="বর্তমান ধাপ" />
        </small>
        <b>
          <Bilingual en="Hearing 3" bn="শুনানি ৩" />
        </b>
        {lawyer && (
          <button onClick={onReview}>
            <Icon name="document" size={17} />
            <Bilingual en="Review with AI" bn="এআই দিয়ে পর্যালোচনা" />
          </button>
        )}
      </div>
    </div>
  );
}

function ClientDashboard({ notify }: { notify: (s: string) => void }) {
  return (
    <>
      <PageHeading
        eyebrow={<Bilingual en="Client portal" bn="মক্কেল পোর্টাল" />}
        title={<Bilingual en="Your Case" bn="আপনার মামলা" />}
        subtitle={
          <Bilingual
            en="A clear view of your case and what comes next."
            bn="আপনার মামলা ও পরবর্তী ধাপের সহজ চিত্র।"
          />
        }
      />
      <CaseHeader />
      <div className="case-layout">
        <div className="panel progress-panel">
          <div className="panel-head">
            <div>
              <h2>
                <Bilingual en="Case progress" bn="মামলার অগ্রগতি" />
              </h2>
              <p>
                <Bilingual en="Three of five stages reached" bn="পাঁচটির মধ্যে তিনটি ধাপে পৌঁছেছে" />
              </p>
            </div>
            <span className="percent">60%</span>
          </div>
          <CaseProgress />
        </div>
        <div className="next-hearing">
          <div className="calendar-large">
            <small>
              <Bilingual en="JAN" bn="জানু" />
            </small>
            <b>
              <Bilingual en="17" bn="১৭" />
            </b>
            <span>
              <Bilingual en="2025" bn="২০২৫" />
            </span>
          </div>
          <div>
            <span className="eyebrow">
              <Bilingual en="Next hearing" bn="পরবর্তী শুনানি" />
            </span>
            <h2>
              <Bilingual en="Friday at 10:30 AM" bn="শুক্রবার সকাল ১০:৩০" />
            </h2>
            <p>
              <Bilingual en="Courtroom 4, Dhaka District Court" bn="আদালতকক্ষ ৪, ঢাকা জেলা আদালত" />
            </p>
          </div>
        </div>
        <div className="panel docs-panel">
          <div className="panel-head">
            <div>
              <h2>
                <Bilingual en="Case documents" bn="মামলার নথি" />
              </h2>
              <p>
                <Bilingual en="Files shared by your lawyer" bn="আপনার আইনজীবীর শেয়ার করা ফাইল" />
              </p>
            </div>
            <span className="count-chip">
              3{" "}
              <span>
                <Bilingual en="files" bn="ফাইল" />
              </span>
            </span>
          </div>
          <Documents notify={notify} />
        </div>
      </div>
    </>
  );
}

function CaseDetail({ notify, onBack }: { notify: (s: string) => void; onBack: () => void }) {
  const { language } = useLanguage();
  useEffect(() => {
    /* Keeps screen entry animation deterministic. */
  }, []);
  return (
    <>
      <button className="back-link" onClick={onBack}>
        <span>←</span>
        <Bilingual en="Back to matters" bn="মামলায় ফিরুন" />
      </button>
      <CaseHeader
        lawyer
        onReview={() => notify(language === "en" ? "AI review prepared" : "এআই পর্যালোচনা প্রস্তুত")}
      />
      <div className="case-layout lawyer-case-layout">
        <div className="panel progress-panel">
          <div className="panel-head">
            <div>
              <h2>
                <Bilingual en="Case progress" bn="মামলার অগ্রগতি" />
              </h2>
              <p>
                <Bilingual en="Updated after the last hearing" bn="শেষ শুনানির পর হালনাগাদ" />
              </p>
            </div>
            <span className="percent">60%</span>
          </div>
          <CaseProgress />
        </div>
        <div className="panel timeline-panel">
          <div className="panel-head">
            <div>
              <h2>
                <Bilingual en="Hearings timeline" bn="শুনানির সময়রেখা" />
              </h2>
              <p>
                <Bilingual en="Court appearances and notes" bn="আদালতে উপস্থিতি ও নোট" />
              </p>
            </div>
            <button className="outline-button small">
              <Icon name="plus" size={16} />
              <Bilingual en="Add hearing" bn="শুনানি যোগ করুন" />
            </button>
          </div>
          <div className="timeline">
            <div className="timeline-item current">
              <span />
              <div>
                <small>
                  <Bilingual en="17 JAN 2025 · Upcoming" bn="১৭ জানুয়ারি ২০২৫ · আসন্ন" />
                </small>
                <b>
                  <Bilingual en="Hearing 3 — Evidence" bn="শুনানি ৩ — সাক্ষ্য" />
                </b>
                <p>
                  <Bilingual
                    en="Plaintiff witness examination. Bring original deed."
                    bn="বাদীপক্ষের সাক্ষী পরীক্ষা। মূল দলিল আনতে হবে।"
                  />
                </p>
              </div>
            </div>
            <div className="timeline-item">
              <span />
              <div>
                <small>
                  <Bilingual en="21 NOV 2024" bn="২১ নভেম্বর ২০২৪" />
                </small>
                <b>
                  <Bilingual en="Hearing 2 — Issues framed" bn="শুনানি ২ — বিচার্য বিষয় নির্ধারণ" />
                </b>
                <p>
                  <Bilingual
                    en="Court framed four issues for trial."
                    bn="আদালত বিচারের জন্য চারটি বিষয় নির্ধারণ করেছেন।"
                  />
                </p>
              </div>
            </div>
            <div className="timeline-item">
              <span />
              <div>
                <small>
                  <Bilingual en="08 OCT 2024" bn="০৮ অক্টোবর ২০২৪" />
                </small>
                <b>
                  <Bilingual en="Hearing 1 — Appearance" bn="শুনানি ১ — হাজিরা" />
                </b>
                <p>
                  <Bilingual en="Defendant entered appearance." bn="বিবাদী হাজির হয়েছেন।" />
                </p>
              </div>
            </div>
          </div>
        </div>
        <div className="panel docs-panel">
          <div className="panel-head">
            <div>
              <h2>
                <Bilingual en="Documents" bn="নথিপত্র" />
              </h2>
              <p>
                <Bilingual en="Case files and court orders" bn="মামলার ফাইল ও আদালতের আদেশ" />
              </p>
            </div>
            <button className="outline-button small">
              <Icon name="plus" size={16} />
              <Bilingual en="Upload" bn="আপলোড" />
            </button>
          </div>
          <Documents notify={notify} />
        </div>
      </div>
    </>
  );
}
