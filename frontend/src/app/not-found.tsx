import Link from "next/link";
import { AuthLayout } from "@/components/AuthLayout";
import { dictionaries } from "@/lib/i18n";
import { getLanguage } from "@/lib/language";

/** Unknown URLs. /logout always works, so a signed-in user is never stuck here. */
export default async function NotFound() {
  const language = await getLanguage();
  const common = dictionaries[language].common;

  return (
    <AuthLayout type="lawyer" language={language}>
      <h2>{common.pageNotFound}</h2>
      <p className="form-intro">{common.pageNotFoundBody}</p>
      <div className="empty-state-actions">
        <Link className="ghost-button" href="/">
          {common.back}
        </Link>
        {/* A plain anchor: a prefetched Link would sign the user out. */}
        <a className="ghost-button" href="/logout">
          {common.signOut}
        </a>
      </div>
    </AuthLayout>
  );
}
