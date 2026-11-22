"use client";

import { useRef } from "react";
import { archiveMatterAction } from "@/app/lawyer/actions";
import type { Dictionary } from "@/lib/i18n";

/** Archive (soft delete) behind a confirm dialog. The backend allows only the lead lawyer. */
export function ArchiveCaseDialog({
  caseId,
  copy,
}: {
  caseId: string;
  copy: Dictionary["caseDetail"]["archive"];
}) {
  const dialog = useRef<HTMLDialogElement>(null);

  return (
    <>
      <button type="button" className="case-action danger" onClick={() => dialog.current?.showModal()}>
        {copy.button}
      </button>
      <dialog ref={dialog} className="confirm-dialog" aria-labelledby={`archive-title-${caseId}`}>
        <h2 id={`archive-title-${caseId}`}>{copy.title}</h2>
        <p>{copy.body}</p>
        <form action={archiveMatterAction} className="confirm-actions">
          <input type="hidden" name="caseId" value={caseId} />
          <input type="hidden" name="archive" value="1" />
          <button type="button" className="ghost-button" onClick={() => dialog.current?.close()}>
            {copy.cancel}
          </button>
          <button type="submit" className="primary-button fit danger">
            {copy.confirm}
          </button>
        </form>
      </dialog>
    </>
  );
}
