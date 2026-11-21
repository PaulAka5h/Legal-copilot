"""Exceptions raised by the legal search model providers (answered as 503 problems)."""


class ProviderNotConfigured(RuntimeError):
    """A model could not be loaded; endpoints answer NOT_CONFIGURED."""


class EmbeddingUnavailable(ProviderNotConfigured):
    """The remote embedder failed for this request; answered as 503."""


class EmbeddingModelMismatch(ProviderNotConfigured):
    """The knowledge base was embedded with another model/version than the query embedder.

    Comparing vectors from different models returns meaningless neighbours, so search
    refuses (503 EMBEDDING_MODEL_MISMATCH) instead of answering.
    """

    def __init__(self, query_model: str, query_version: int, stored: list[tuple[str, int]]):
        self.query_model, self.query_version, self.stored = query_model, query_version, stored
        found = ", ".join(f"{m} v{v}" for m, v in stored)
        super().__init__(
            f"legal knowledge base is embedded with {found}, but queries are embedded with "
            f"{query_model} v{query_version}; re-embed the knowledge base (python -m app.rag.embed "
            "reembed) or change EMBEDDING_PROVIDER"
        )
