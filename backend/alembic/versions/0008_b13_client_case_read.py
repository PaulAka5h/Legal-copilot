"""Allow clients to read their active open cases."""

from alembic import op

revision = "0008_b13_client_case_read"
down_revision = "0007_b13_client_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(
        """
        CREATE POLICY client_read_open_cases ON public.cases
        FOR SELECT TO app_user
        USING (status = 'open' AND app.is_client_member(id))
        """
    )
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute("DROP POLICY IF EXISTS client_read_open_cases ON public.cases")
    op.execute("RESET ROLE")
