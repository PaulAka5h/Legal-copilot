import Link from "next/link";
import { updateProfileAction } from "@/app/lawyer/actions";
import type { LawyerProfileDetail } from "@/lib/api/lawyer";
import type { Dictionary } from "@/lib/i18n";

/** Name, phone, preferred language and organization display fields. Email is read-only. */
export function ProfileForm({
  detail,
  copy,
  error,
}: {
  detail: LawyerProfileDetail;
  copy: Dictionary["settings"];
  error: boolean;
}) {
  return (
    <form action={updateProfileAction} className="profile-form">
      {error ? (
        <p className="form-error" role="alert">
          {copy.profileError}
        </p>
      ) : null}
      <p className="field-hint">{copy.editProfileBody}</p>
      <div className="edit-case-grid">
        <label className="block">
          <span className="field-label">{copy.name}</span>
          <input name="fullName" required maxLength={200} autoComplete="name" defaultValue={detail.fullName} />
        </label>
        <label className="block">
          <span className="field-label">{copy.email}</span>
          <input value={detail.email} disabled readOnly aria-readonly="true" />
        </label>
        <label className="block">
          <span className="field-label">{copy.phone}</span>
          <input
            name="phone"
            type="tel"
            maxLength={30}
            pattern="[0-9+()\- ]*"
            autoComplete="tel"
            defaultValue={detail.phone}
          />
        </label>
        <label className="block">
          <span className="field-label">{copy.preferredLanguage}</span>
          <select name="preferredLanguage" defaultValue={detail.preferredLanguage}>
            <option value="en">{copy.languageEn}</option>
            <option value="bn">{copy.languageBn}</option>
          </select>
        </label>
        <label className="block">
          <span className="field-label">{copy.chamber}</span>
          <input name="chamberName" maxLength={200} defaultValue={detail.chamberName} />
        </label>
        <label className="block">
          <span className="field-label">{copy.organization}</span>
          <input
            name="organizationName"
            maxLength={200}
            required={detail.canEditOrganization}
            disabled={!detail.canEditOrganization}
            defaultValue={detail.organizationName}
          />
          {detail.canEditOrganization ? null : <span className="field-hint">{copy.organizationOwnerOnly}</span>}
        </label>
      </div>
      <div className="confirm-actions">
        <Link className="ghost-button" href="/lawyer/settings">
          {copy.cancel}
        </Link>
        <button className="primary-button fit" type="submit">
          {copy.saveProfile}
        </button>
      </div>
    </form>
  );
}
