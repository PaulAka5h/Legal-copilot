import Link from "next/link";
import { editMatterAction } from "@/app/lawyer/actions";
import type { Localized, Matter, MatterStatus } from "@/lib/api/lawyer";
import { pick, type Dictionary, type Language } from "@/lib/i18n";

const STATUSES: MatterStatus[] = ["active", "on_hold", "closed"];

/** Edit title, case type, court and status. Saved with an audit record by the backend. */
export function EditCasePanel({
  matter,
  language,
  copy,
  statusLabels,
  caseTypes,
  courts,
  error,
}: {
  matter: Matter;
  language: Language;
  copy: Dictionary["caseDetail"]["edit"];
  statusLabels: Dictionary["matters"]["status"];
  caseTypes: Localized[];
  courts: Localized[];
  error: string | null;
}) {
  const path = `/lawyer/matters/${encodeURIComponent(matter.id)}`;

  return (
    <form action={editMatterAction} id="edit-case" className="panel edit-case-panel">
      <input type="hidden" name="caseId" value={matter.id} />
      <div className="panel-head">
        <div>
          <h2>{copy.title}</h2>
          <p>{copy.body}</p>
        </div>
      </div>
      {error ? (
        <p className="form-error" role="alert">
          {error === "closed" ? copy.closedLocked : error === "archived" ? copy.archivedLocked : copy.error}
        </p>
      ) : null}
      <div className="edit-case-grid">
        <label className="block">
          <span className="field-label">{copy.fieldTitle}</span>
          <input name="title" required maxLength={300} defaultValue={pick(matter.title, language)} />
        </label>
        <label className="block">
          <span className="field-label">{copy.fieldCaseType}</span>
          <input
            name="caseType"
            required
            maxLength={100}
            list="case-type-options"
            defaultValue={pick(matter.caseType, language)}
          />
          <datalist id="case-type-options">
            {caseTypes.map((item) => (
              <option key={item.en} value={pick(item, language)} />
            ))}
          </datalist>
        </label>
        <label className="block">
          <span className="field-label">{copy.fieldCourt}</span>
          <input name="court" maxLength={200} list="court-options" defaultValue={pick(matter.court, language)} />
          <datalist id="court-options">
            {courts.map((item) => (
              <option key={item.en} value={pick(item, language)} />
            ))}
          </datalist>
        </label>
        <label className="block">
          <span className="field-label">{copy.fieldStatus}</span>
          <select name="status" defaultValue={matter.status}>
            {STATUSES.map((status) => (
              <option key={status} value={status}>
                {statusLabels[status]}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="confirm-actions">
        <Link className="ghost-button" href={path}>
          {copy.cancel}
        </Link>
        <button className="primary-button fit" type="submit">
          {copy.save}
        </button>
      </div>
    </form>
  );
}
