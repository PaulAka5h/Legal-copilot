import { signOut } from "@/app/actions";
import { dictionaries, type Language } from "@/lib/i18n";
import { Icon } from "./Icon";
import { Logo } from "./Logo";

export function NotConfigured({ language, title }: { language: Language; title: string }) {
  const copy = dictionaries[language].notConfigured;
  const common = dictionaries[language].common;

  return (
    <main className="grid min-h-screen place-items-center bg-cream p-6">
      <div className="w-full max-w-[560px] rounded-[14px] border border-black/5 bg-white p-9 shadow-card">
        <Logo language={language} />
        <span className="eyebrow mt-8 block">{copy.eyebrow}</span>
        <h1 className="mt-2 font-serif text-[35px] leading-none text-ink">{copy.title}</h1>
        <h2 className="mt-3 text-sm font-bold text-ink">{title}</h2>
        <p className="mt-2 text-[13px] leading-6 text-muted">{copy.body}</p>
        <form action={signOut} className="mt-6">
          <button className="primary-button fit" type="submit">
            {common.signOut}
            <Icon name="arrow" size={18} />
          </button>
        </form>
      </div>
    </main>
  );
}
