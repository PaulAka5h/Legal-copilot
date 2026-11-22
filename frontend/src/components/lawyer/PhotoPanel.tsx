import { removePhotoAction, uploadPhotoAction } from "@/app/lawyer/actions";
import { Avatar, lawyerPhotoUrl } from "@/components/Avatar";
import type { Dictionary } from "@/lib/i18n";

const MESSAGES = {
  too_large: "photoTooLarge",
  wrong_type: "photoWrongType",
  invalid: "photoInvalid",
  error: "photoError",
  NOT_CONFIGURED: "photoNotConfigured",
} as const;

/** Upload, replace or remove the profile photo; initials are shown when there is none. */
export function PhotoPanel({
  name,
  photoId,
  result,
  copy,
}: {
  name: string;
  photoId: string | null;
  result: string | undefined;
  copy: Dictionary["lawyerProfile"];
}) {
  const errorKey = result && result in MESSAGES ? MESSAGES[result as keyof typeof MESSAGES] : null;
  return (
    <section className="panel" id="photo">
      <div className="panel-head">
        <div>
          <h2>{copy.photoTitle}</h2>
          <p>{copy.photoHint}</p>
        </div>
      </div>
      {result === "saved" || result === "removed" ? (
        <p className="success-note" role="status">
          {result === "saved" ? copy.photoSaved : copy.photoRemoved}
        </p>
      ) : null}
      {errorKey ? (
        <p className="form-error" role="alert">
          {copy[errorKey]}
        </p>
      ) : null}
      <div className="photo-row">
        <Avatar name={name} src={lawyerPhotoUrl(photoId, 512)} size={96} />
        <form action={uploadPhotoAction} className="photo-upload">
          <label className="block">
            <span className="field-label">{photoId ? copy.replacePhoto : copy.uploadPhoto}</span>
            <input type="file" name="photo" required accept="image/jpeg,image/png,image/webp" />
          </label>
          <button className="primary-button fit" type="submit">
            {photoId ? copy.replacePhoto : copy.uploadPhoto}
          </button>
        </form>
        {photoId ? (
          <form action={removePhotoAction}>
            <button className="outline-button" type="submit">
              {copy.removePhoto}
            </button>
          </form>
        ) : null}
      </div>
    </section>
  );
}
