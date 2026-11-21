import Link from "next/link";
import { Icon } from "@/components/Icon";
import { SignOutButton } from "@/components/SignOutButton";
import { dictionaries } from "@/lib/i18n";
import { getLanguage } from "@/lib/language";

/** Not-found body for the signed-in areas: a way back and a way out. */
export async function NotFoundPanel({ backHref }: { backHref: string }) {
  const common = dictionaries[await getLanguage()].common;

  return (
    <div className="panel empty-state">
      <Icon name="document" size={28} />
      <h1>{common.pageNotFound}</h1>
      <p>{common.pageNotFoundBody}</p>
      <div className="empty-state-actions">
        <Link className="ghost-button" href={backHref}>
          {common.back}
        </Link>
        <SignOutButton label={common.signOut} />
      </div>
    </div>
  );
}
