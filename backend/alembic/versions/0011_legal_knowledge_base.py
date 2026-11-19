"""Legal knowledge base: sources, versions, sections, chunks (shared, not case-scoped).

Follows DOCS/database.md sections 7 and 12.4, plus the approved `legal_sections`
table (2026-11-20) that holds per-section text, bn/en linking
(`canonical_section_id`), in-force status, and effective dates.

Access (database.md 12.4):
- Any active lawyer (users.role = 'lawyer', status 'active') may SELECT, via app_user.
- Only app_admin_ingest may write. Nothing may DELETE: history is kept (Rule 6).
- Search must exclude versions whose review_status is not 'approved'.

Revision ID: 0011_legal_knowledge_base
Revises: 0010_phase7_hearings_reassessment
Create Date: 2026-11-20
"""

from alembic import op

revision = "0011_legal_knowledge_base"
down_revision = "0010_phase7_hearings_reassessment"
branch_labels = None
depends_on = None

TABLES = ("legal_sources", "legal_source_versions", "legal_sections", "legal_chunks")
STATUS_CHECK = "('in_force','amended','repealed','partly_repealed','unknown')"


def upgrade() -> None:
    # Extensions need the migration connection's privileges, not app_owner's.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("GRANT USAGE ON SCHEMA public TO app_admin_ingest")
    op.execute("GRANT USAGE ON SCHEMA app TO app_admin_ingest")

    op.execute("SET ROLE app_owner")
    _create_tables()
    _create_indexes()
    _create_functions()
    _create_policies()
    _grant_access()
    op.execute("RESET ROLE")


def _create_tables() -> None:
    op.execute(
        f"""
        CREATE TABLE public.legal_sources (
          id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          kind              text NOT NULL CHECK (kind IN ('constitution','act','ordinance','code','rule',
                                                          'regulation','notification','judgment','other')),
          title             text NOT NULL,
          short_title       text,
          citation          text,
          number_year       text,
          issuing_authority text,
          court             text,
          bench             text,
          decision_date     date,
          language          text NOT NULL CHECK (language IN ('bn','en','both')),
          current_status    text NOT NULL DEFAULT 'unknown' CHECK (current_status IN {STATUS_CHECK}),
          status_verified_on date,
          status_note       text,
          source_url        text,
          source_name       text NOT NULL,
          external_id       text NOT NULL,
          licence_note      text,
          created_at        timestamptz NOT NULL DEFAULT now(),
          UNIQUE (source_name, external_id, language)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE public.legal_source_versions (
          id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          legal_source_id uuid NOT NULL REFERENCES public.legal_sources(id),
          version_no      int NOT NULL CHECK (version_no > 0),
          effective_from  date,
          effective_to    date,
          full_text       text,
          content_sha256  bytea NOT NULL,
          amendment_note  text,
          ingested_at     timestamptz NOT NULL DEFAULT now(),
          ingested_by     text NOT NULL,
          review_status   text NOT NULL DEFAULT 'pending'
                          CHECK (review_status IN ('pending','approved','rejected')),
          reviewed_by     uuid REFERENCES public.users(id),
          reviewed_at     timestamptz,
          is_current      boolean NOT NULL DEFAULT false,
          UNIQUE (legal_source_id, version_no),
          CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE public.legal_sections (
          id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          legal_source_version_id uuid NOT NULL REFERENCES public.legal_source_versions(id),
          section_key             text NOT NULL,
          position                int NOT NULL CHECK (position >= 0),
          section_number          text,
          heading                 text,
          chapter_number          text,
          chapter_title           text,
          language                text NOT NULL CHECK (language IN ('bn','en')),
          text                    text NOT NULL,
          canonical_section_id    uuid NOT NULL,
          status                  text NOT NULL DEFAULT 'unknown' CHECK (status IN {STATUS_CHECK}),
          status_basis            text,
          effective_from          date,
          effective_to            date,
          source_url              text NOT NULL,
          content_hash            text NOT NULL,
          created_at              timestamptz NOT NULL DEFAULT now(),
          UNIQUE (legal_source_version_id, section_key),
          CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE public.legal_chunks (
          id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          legal_source_version_id uuid NOT NULL REFERENCES public.legal_source_versions(id),
          legal_section_id        uuid NOT NULL REFERENCES public.legal_sections(id),
          provision_label         text,
          chunk_index             int NOT NULL CHECK (chunk_index >= 0),
          text                    text NOT NULL,
          token_count             int NOT NULL CHECK (token_count > 0),
          content_hash            text NOT NULL,
          tsv                     tsvector GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED,
          embedding               vector(1024),
          embedding_model         text NOT NULL,
          embedding_version       int NOT NULL,
          embedded_at             timestamptz,
          is_active               boolean NOT NULL DEFAULT true,
          created_at              timestamptz NOT NULL DEFAULT now(),
          UNIQUE (legal_section_id, chunk_index)
        )
        """
    )


def _create_indexes() -> None:
    statements = (
        "CREATE INDEX ix_legal_sources_kind_status ON public.legal_sources (kind, current_status)",
        "CREATE INDEX ix_legal_sources_title_trgm ON public.legal_sources USING gin (title gin_trgm_ops)",
        """CREATE UNIQUE INDEX ux_legal_source_versions_current
           ON public.legal_source_versions (legal_source_id) WHERE is_current""",
        "CREATE INDEX ix_legal_sections_canonical ON public.legal_sections (canonical_section_id)",
        "CREATE INDEX ix_legal_sections_version_position ON public.legal_sections (legal_source_version_id, position)",
        "CREATE INDEX ix_legal_sections_status ON public.legal_sections (status)",
        """CREATE INDEX ix_legal_chunks_embedding_hnsw
           ON public.legal_chunks USING hnsw (embedding vector_cosine_ops)""",
        "CREATE INDEX ix_legal_chunks_tsv ON public.legal_chunks USING gin (tsv)",
        "CREATE INDEX ix_legal_chunks_version ON public.legal_chunks (legal_source_version_id)",
        "CREATE INDEX ix_legal_chunks_section ON public.legal_chunks (legal_section_id)",
        """CREATE INDEX ix_legal_chunks_pending_embedding
           ON public.legal_chunks (id) WHERE embedding IS NULL AND is_active""",
    )
    for statement in statements:
        op.execute(statement)


def _create_functions() -> None:
    op.execute(
        """
        CREATE FUNCTION app.is_active_lawyer() RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM public.users u
            WHERE u.id = app.current_user_id()
              AND u.role = 'lawyer'
              AND u.status = 'active')
        $$
        """
    )
    op.execute("REVOKE EXECUTE ON FUNCTION app.is_active_lawyer() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.is_active_lawyer() TO app_user")


def _create_policies() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_lawyer_read ON public.{table}
            FOR SELECT TO app_user
            USING (app.is_active_lawyer())
            """
        )
        op.execute(
            f"""
            CREATE POLICY {table}_ingest_read ON public.{table}
            FOR SELECT TO app_admin_ingest USING (true)
            """
        )
        op.execute(
            f"""
            CREATE POLICY {table}_ingest_insert ON public.{table}
            FOR INSERT TO app_admin_ingest WITH CHECK (true)
            """
        )
    # Only tables with column-limited UPDATE grants need an UPDATE policy.
    for table in ("legal_sources", "legal_source_versions", "legal_chunks"):
        op.execute(
            f"""
            CREATE POLICY {table}_ingest_update ON public.{table}
            FOR UPDATE TO app_admin_ingest USING (true) WITH CHECK (true)
            """
        )


def _grant_access() -> None:
    statements = [f"GRANT SELECT ON public.{t} TO app_user" for t in TABLES]
    statements += [f"GRANT SELECT, INSERT ON public.{t} TO app_admin_ingest" for t in TABLES]
    statements += [
        # Section text is immutable; a changed section becomes a new source version.
        "GRANT UPDATE (current_status, status_note, status_verified_on, title, short_title, "
        "number_year, source_url) ON public.legal_sources TO app_admin_ingest",
        "GRANT UPDATE (is_current, effective_to) ON public.legal_source_versions TO app_admin_ingest",
        "GRANT UPDATE (embedding, embedding_model, embedding_version, embedded_at, is_active) "
        "ON public.legal_chunks TO app_admin_ingest",
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE public.{table}")  # drops its policies, indexes, grants
    op.execute("DROP FUNCTION app.is_active_lawyer()")
    op.execute("RESET ROLE")
    op.execute("REVOKE USAGE ON SCHEMA app FROM app_admin_ingest")
    op.execute("REVOKE USAGE ON SCHEMA public FROM app_admin_ingest")
    # The vector and pg_trgm extensions belong to 0001_phase1_baseline and stay.
