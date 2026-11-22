"""Per-organization cache of LLM query rewrites (app.rag.search.query_rewrite).

A search-box query or a case-fact statement that was rewritten once (Bangla, English,
keywords) is not sent to the LLM again: the variants are stored under
sha256(prompt version, LLM model, NFC query). The query itself is not stored; the variants
are derived from it (they can paraphrase case facts), so rows are scoped to the
organization and readable/insertable only by its active owners and lawyers (forced row
level security). Rows are immutable cache entries: no UPDATE, no client access.

Revision ID: 0022_query_rewrite_cache
Revises: 0021_e5_small_embeddings
Create Date: 2026-11-22
"""

from alembic import op

revision = "0022_query_rewrite_cache"
down_revision = "0021_e5_small_embeddings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(
        """
        CREATE TABLE public.query_rewrites (
          organization_id uuid NOT NULL REFERENCES public.organizations(id),
          cache_key       text NOT NULL CHECK (cache_key ~ '^[0-9a-f]{64}$'),
          variants        jsonb NOT NULL CHECK (jsonb_typeof(variants) = 'array'
                                                AND jsonb_array_length(variants) BETWEEN 1 AND 3),
          created_at      timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (organization_id, cache_key)
        )
        """
    )
    op.execute("ALTER TABLE public.query_rewrites ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.query_rewrites FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY query_rewrites_lawyer_read ON public.query_rewrites "
        "FOR SELECT TO app_user USING (app.is_org_lawyer(organization_id))"
    )
    op.execute(
        "CREATE POLICY query_rewrites_lawyer_insert ON public.query_rewrites "
        "FOR INSERT TO app_user WITH CHECK (app.is_org_lawyer(organization_id))"
    )
    op.execute("GRANT SELECT, INSERT ON public.query_rewrites TO app_user")
    op.execute("SELECT app.ensure_owner_policies()")  # app_owner without BYPASSRLS (Neon; 0019)
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute("DROP TABLE public.query_rewrites")
    op.execute("RESET ROLE")
