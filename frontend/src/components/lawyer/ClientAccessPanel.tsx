import Link from "next/link";
import { linkClientToCaseAction } from "@/app/lawyer/actions";
import { Field } from "@/components/Field";
import { Icon } from "@/components/Icon";
import type { LinkableClient, LinkClientResult } from "@/lib/api/lawyer";
import type { Dictionary } from "@/lib/i18n";

/** Lead lawyer adds an existing client (with a portal login) to this case. */
export function ClientAccessPanel({
  caseId,
  clients,
  locked,
  result,
  copy,
  notConfigured,
}: {
  caseId: string;
  clients: LinkableClient[];
  locked: boolean;
  result: LinkClientResult | null;
  copy: Dictionary["caseDetail"]["clientAccess"];
  notConfigured: string;
}) {
  const message =
    result === "ok"
      ? { role: "status", className: "mock-note", text: copy.linked }
      : result === "no_login"
        ? { role: "alert", className: "form-error", text: copy.noLogin }
        : result === "NOT_CONFIGURED"
          ? { role: "status", className: "mock-note", text: notConfigured }
          : result === "error"
            ? { role: "alert", className: "form-error", text: copy.error }
            : null;

  return (
    <div className="panel client-access-panel" id="client-access">
      <div className="panel-head">
        <div>
          <h2>{copy.title}</h2>
          <p>{copy.body}</p>
        </div>
      </div>
      {message ? (
        <p className={message.className} role={message.role}>
          {message.text}
        </p>
      ) : null}
      {clients.length === 0 ? (
        <p className="empty-note">
          {copy.none}{" "}
          <Link href="/lawyer/clients/new">{copy.newClient}</Link>
        </p>
      ) : (
        <form action={linkClientToCaseAction} className="client-access-form">
          <input type="hidden" name="caseId" value={caseId} />
          <Field label={copy.label}>
            <select name="clientId" required defaultValue="" disabled={locked}>
              <option value="" disabled>
                {copy.placeholder}
              </option>
              {clients.map((client) => (
                <option key={client.id} value={client.id}>
                  {client.name}
                </option>
              ))}
            </select>
          </Field>
          <button className="primary-button fit" type="submit" disabled={locked}>
            {copy.submit}
            <Icon name="plus" size={18} />
          </button>
        </form>
      )}
    </div>
  );
}
