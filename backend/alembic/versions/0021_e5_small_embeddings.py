"""Legal chunk embeddings of any supported dimension: vector(1024) -> vector + one HNSW index per dimension.

EMBEDDING_PROVIDER can now be switched between e5_small_onnx (intfloat/multilingual-e5-small,
384 dims) and the 1024-dim providers (local / hf_api: multilingual-e5-large; gemini:
gemini-embedding-001) without a schema change. Stored vectors are kept as they are; each
chunk still records its embedding_model/embedding_version, and search's mismatch guard
still refuses a knowledge base embedded with another model. Switching models means
re-embedding (`python -m app.rag.embed reembed --provider ...`).

pgvector HNSW needs a fixed dimension, so each dimension gets a partial expression index:
  hnsw ((embedding::vector(N)) vector_cosine_ops) WHERE vector_dims(embedding) = N
and the dense query uses exactly that expression and predicate (app.rag.search.retrieval).

downgrade: back to vector(1024) with the original index; vectors of any other dimension are
cleared first (re-embed them with a 1024-dim provider).
"""

from alembic import op

revision = "0021_e5_small_embeddings"
down_revision = "0020_client_password_onboarding"
branch_labels = None
depends_on = None

DIMENSIONS = (384, 1024)


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.ix_legal_chunks_embedding_hnsw")
    op.execute("ALTER TABLE public.legal_chunks ALTER COLUMN embedding TYPE vector")
    for dim in DIMENSIONS:
        op.execute(
            f"""CREATE INDEX ix_legal_chunks_embedding_hnsw_{dim}
                ON public.legal_chunks USING hnsw ((embedding::vector({dim})) vector_cosine_ops)
                WHERE vector_dims(embedding) = {dim}"""
        )


def downgrade() -> None:
    for dim in DIMENSIONS:
        op.execute(f"DROP INDEX IF EXISTS public.ix_legal_chunks_embedding_hnsw_{dim}")
    op.execute(
        """UPDATE public.legal_chunks SET embedding = NULL, embedded_at = NULL
           WHERE embedding IS NOT NULL AND vector_dims(embedding) <> 1024"""
    )
    op.execute("ALTER TABLE public.legal_chunks ALTER COLUMN embedding TYPE vector(1024)")
    op.execute(
        """CREATE INDEX ix_legal_chunks_embedding_hnsw
           ON public.legal_chunks USING hnsw (embedding vector_cosine_ops)"""
    )
