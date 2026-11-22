import Link from "next/link";
import { updateProfileAction } from "@/app/lawyer/actions";
import {
  PRACTICE_AREAS,
  SPOKEN_LANGUAGES,
  VISIBLE_FIELDS,
  type LawyerProfileDetail,
} from "@/lib/api/lawyerTypes";
import type { Dictionary } from "@/lib/i18n";

function CheckGroup<T extends string>({
  legend,
  hint,
  name,
  options,
  labels,
  checked,
}: {
  legend: string;
  hint?: string;
  name: string;
  options: readonly T[];
  labels: Record<T, string>;
  checked: readonly T[];
}) {
  return (
    <fieldset className="profile-checks">
      <legend className="field-label">{legend}</legend>
      {hint ? <span className="field-hint">{hint}</span> : null}
      <div>
        {options.map((option) => (
          <label key={option}>
            <input type="checkbox" name={name} value={option} defaultChecked={checked.includes(option)} />
            {labels[option]}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/** Account, professional details and client visibility. Login email is read-only. */
export function ProfileForm({
  detail,
  copy,
  profileCopy,
  error,
}: {
  detail: LawyerProfileDetail;
  copy: Dictionary["settings"];
  profileCopy: Dictionary["lawyerProfile"];
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

      <h3 className="profile-subhead">{profileCopy.professionalTitle}</h3>
      <p className="field-hint">{profileCopy.professionalHint}</p>
      <div className="edit-case-grid">
        <label className="block">
          <span className="field-label">{profileCopy.barEnrollment}</span>
          <input name="barEnrollmentNo" maxLength={50} defaultValue={detail.barEnrollmentNo} />
        </label>
        <label className="block">
          <span className="field-label">{profileCopy.yearsExperience}</span>
          <input
            name="yearsExperience"
            type="number"
            inputMode="numeric"
            min={0}
            max={80}
            step={1}
            defaultValue={detail.yearsExperience ?? ""}
          />
        </label>
        <label className="block">
          <span className="field-label">{profileCopy.publicPhone}</span>
          <input
            name="publicPhone"
            type="tel"
            maxLength={20}
            placeholder="+8801712345678"
            autoComplete="tel"
            defaultValue={detail.publicPhone}
          />
          <span className="field-hint">{profileCopy.publicPhoneHint}</span>
        </label>
        <label className="block">
          <span className="field-label">{profileCopy.publicEmail}</span>
          <input name="publicEmail" type="email" maxLength={254} autoComplete="email" defaultValue={detail.publicEmail} />
          <span className="field-hint">{profileCopy.publicEmailHint}</span>
        </label>
        <label className="block wide">
          <span className="field-label">{profileCopy.courts}</span>
          <textarea name="courts" rows={3} maxLength={1600} defaultValue={detail.courts.join("\n")} />
          <span className="field-hint">{profileCopy.courtsHint}</span>
        </label>
        <label className="block wide">
          <span className="field-label">{profileCopy.officeAddress}</span>
          <textarea name="officeAddress" rows={2} maxLength={300} defaultValue={detail.officeAddress} />
        </label>
        <label className="block wide">
          <span className="field-label">{profileCopy.bio}</span>
          <textarea name="bio" rows={4} maxLength={500} defaultValue={detail.bio} />
          <span className="field-hint">{profileCopy.bioHint}</span>
        </label>
      </div>
      <CheckGroup
        legend={profileCopy.practiceAreas}
        name="practiceAreas"
        options={PRACTICE_AREAS}
        labels={profileCopy.practiceAreaOptions}
        checked={detail.practiceAreas}
      />
      <CheckGroup
        legend={profileCopy.languages}
        name="languages"
        options={SPOKEN_LANGUAGES}
        labels={profileCopy.languageOptions}
        checked={detail.languages}
      />

      <CheckGroup
        legend={profileCopy.visibilityTitle}
        hint={profileCopy.visibilityHint}
        name="visibleFields"
        options={VISIBLE_FIELDS}
        labels={profileCopy.fields}
        checked={detail.visibleFields}
      />

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
