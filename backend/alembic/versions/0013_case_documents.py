"""Case documents and versioned extracted pages (Step C1).

documents: original files in object storage (key cases/{case_id}/documents/{id}).
extracted_pages: NFC page text, one row per page per version; lawyer corrections
add a version, never overwrite. OCR confidence is stored per page.

Access: active lawyer members of the case read; writes also require the case not
to be closed (app.can_write_case). No client policy (clients get shared documents
through client_shared_documents). No DELETE grant. Composite (id, case_id) keys
stop a page from pointing at another case's document.

Revision ID: 0013_case_documents
Revises: 0012_legal_version_approval
Create Date: 2026-11-20
"""

from alembic import op

revision = "0013_case_documents"
down_revision = "0012_legal_version_approval"
branch_labels = None
depends_on = None

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(
        """
        CREATE FUNCTION app.can_write_case(p_case uuid) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT app.is_lawyer_member(p_case)
             AND EXISTS (SELECT 1 FROM public.cases c WHERE c.id = p_case AND c.status <> 'closed')
        $$
        """
    )
    op.execute("REVOKE EXECUTE ON FUNCTION app.can_write_case(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.can_write_case(uuid) TO app_user")

    op.execute(
        f"""
        CREATE TABLE public.documents (
          id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          case_id           uuid NOT NULL REFERENCES public.cases(id),
          organization_id   uuid NOT NULL REFERENCES public.organizations(id),
          title             text NOT NULL CHECK (length(title) BETWEEN 1 AND 300),
          original_filename text NOT NULL CHECK (length(original_filename) BETWEEN 1 AND 255),
          mime_type         text NOT NULL
                            CHECK (mime_type IN ('application/pdf','image/png','image/jpeg','image/tiff')),
          size_bytes        bigint NOT NULL CHECK (size_bytes > 0 AND size_bytes <= {MAX_UPLOAD_BYTES}),
          sha256            bytea NOT NULL CHECK (octet_length(sha256) = 32),
          storage_key       text NOT NULL UNIQUE,
          doc_type          text,
          language          text CHECK (language IN ('bn','en','mixed','unknown')),
          page_count        int CHECK (page_count >= 0),
          scan_status       text NOT NULL DEFAULT 'pending'
                            CHECK (scan_status IN ('pending','clean','infected','failed','not_configured')),
          processing_status text NOT NULL DEFAULT 'queued'
                            CHECK (processing_status IN ('queued','processing','ready','needs_review','failed','deleted')),
          processing_error  text,  -- error code only, never document text
          uploaded_by       uuid NOT NULL REFERENCES public.users(id),
          uploaded_at       timestamptz NOT NULL DEFAULT now(),
          processed_at      timestamptz,
          deleted_at        timestamptz,
          UNIQUE (case_id, sha256),
          UNIQUE (id, case_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_documents_case_status ON public.documents (case_id, processing_status)")

    op.execute(
        """
        CREATE TABLE public.extracted_pages (
          id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          document_id     uuid NOT NULL,
          case_id         uuid NOT NULL,
          organization_id uuid NOT NULL,
          page_no         int NOT NULL CHECK (page_no >= 1),
          version         int NOT NULL DEFAULT 1 CHECK (version >= 1),
          is_current      boolean NOT NULL DEFAULT true,
          text            text NOT NULL,
          source_method   text NOT NULL CHECK (source_method IN ('text_layer','ocr','lawyer_edit')),
          ocr_engine      text,
          ocr_confidence  real CHECK (ocr_confidence IS NULL OR ocr_confidence BETWEEN 0 AND 1),
          quality_flag    text NOT NULL DEFAULT 'ok'
                          CHECK (quality_flag IN ('ok','needs_review','poor','handwriting_suspected')),
          language        text CHECK (language IN ('bn','en','mixed','unknown')),
          edited_by       uuid REFERENCES public.users(id),
          supersedes_id   uuid REFERENCES public.extracted_pages(id),
          created_at      timestamptz NOT NULL DEFAULT now(),
          FOREIGN KEY (document_id, case_id) REFERENCES public.documents(id, case_id),
          UNIQUE (document_id, page_no, version),
          UNIQUE (id, case_id),
          CHECK ((source_method = 'ocr') = (ocr_engine IS NOT NULL)),
          CHECK ((source_method = 'lawyer_edit') = (edited_by IS NOT NULL)),
          CHECK ((version = 1) = (supersedes_id IS NULL))
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX ux_extracted_pages_current ON public.extracted_pages (document_id, page_no) "
        "WHERE is_current"
    )
    op.execute(
        "CREATE INDEX ix_extracted_pages_case_quality ON public.extracted_pages (case_id, quality_flag) "
        "WHERE is_current"
    )

    for table in ("documents", "extracted_pages"):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_lawyer_read ON public.{table} "
            "FOR SELECT TO app_user USING (app.is_lawyer_member(case_id))"
        )
        op.execute(
            f"CREATE POLICY {table}_lawyer_insert ON public.{table} "
            "FOR INSERT TO app_user WITH CHECK (app.can_write_case(case_id))"
        )
        op.execute(
            f"CREATE POLICY {table}_lawyer_update ON public.{table} "
            "FOR UPDATE TO app_user USING (app.can_write_case(case_id)) WITH CHECK (app.can_write_case(case_id))"
        )

    op.execute("GRANT SELECT, INSERT ON public.documents, public.extracted_pages TO app_user")
    op.execute(
        "GRANT UPDATE (title, doc_type, language, page_count, scan_status, processing_status, "
        "processing_error, processed_at) ON public.documents TO app_user"
    )
    op.execute("GRANT UPDATE (is_current) ON public.extracted_pages TO app_user")
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute("DROP TABLE public.extracted_pages")
    op.execute("DROP TABLE public.documents")
    op.execute("DROP FUNCTION app.can_write_case(uuid)")
    op.execute("RESET ROLE")
