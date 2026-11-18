"""Vector and Keyword Database Storage Client for Legal Knowledge Base (pgvector & in-memory).

Supports:
1. InMemoryVectorStore: Exact cosine similarity, metadata filtering, keyword search, exact section match.
2. PgVectorStore: PostgreSQL 16 + pgvector 0.8+ client:
   - Dense vector cosine similarity (vector_cosine_ops)
   - Sparse keyword search using PostgreSQL full-text search (tsvector + GIN)
   - Exact section identifier search
   - Amendment-aware filtering (is_current, effective_from/to)
   - Parent section chunk recovery
   - Initial query-time session tuning: hnsw.ef_search, hnsw.iterative_scan, etc.
"""

from abc import ABC, abstractmethod
import json
from typing import Any, Dict, List, Optional
from uuid import UUID
import numpy as np
from pydantic import BaseModel
from backend.src.legal_kb.normalizer import extract_section_numbers, normalize_to_en_digits
from backend.src.legal_kb.schemas import LegalChunkPayload, LegalLanguage


class VectorSearchResult(BaseModel):
    chunk: LegalChunkPayload
    score: float  # Cosine similarity (1.0 = identical) or text rank
    retrieval_type: str = "dense"  # "dense", "sparse", "exact"


class BaseVectorStore(ABC):
    @abstractmethod
    def add_chunks(self, chunks: List[LegalChunkPayload], embeddings: List[List[float]]) -> int:
        """Store chunks alongside their embeddings."""
        pass

    @abstractmethod
    def search_dense(
        self,
        query_embedding: List[float],
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """Search top-k most similar chunks using dense vector cosine similarity."""
        pass

    @abstractmethod
    def search_sparse(
        self,
        query_text: str,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """Search top-k relevant chunks using sparse full-text keyword retrieval."""
        pass

    @abstractmethod
    def search_exact_section(
        self,
        section_number: str,
        act_id: Optional[str] = None,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """Search exact section provisions."""
        pass

    @abstractmethod
    def get_parent_section_chunks(self, chunk: LegalChunkPayload) -> List[LegalChunkPayload]:
        """Retrieve all sibling and parent chunks associated with a section."""
        pass


class InMemoryVectorStore(BaseVectorStore):
    """In-memory vector store implementing exact cosine distance and in-memory full-text search."""

    def __init__(self):
        self._chunks: List[LegalChunkPayload] = []
        self._embeddings: List[np.ndarray] = []

    def add_chunks(self, chunks: List[LegalChunkPayload], embeddings: List[List[float]]) -> int:
        if len(chunks) != len(embeddings):
            raise ValueError("Chunks count must match embeddings count")

        for chunk, emb in zip(chunks, embeddings):
            vec = np.array(emb, dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            self._chunks.append(chunk)
            self._embeddings.append(vec)
        return len(chunks)

    def _apply_filters(self, chunk: LegalChunkPayload, filters: Optional[Dict[str, Any]]) -> bool:
        if not filters:
            return True
        for k, v in filters.items():
            if hasattr(chunk, k) and getattr(chunk, k) != v:
                return False
            if chunk.metadata.get(k) != v and k not in chunk.__dict__:
                return False
        return True

    def search_dense(
        self,
        query_embedding: List[float],
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        if not self._chunks:
            return []

        q_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        matrix = np.vstack(self._embeddings)
        scores = np.dot(matrix, q_vec)

        ranked_indices = np.argsort(scores)[::-1]
        results: List[VectorSearchResult] = []

        for idx in ranked_indices:
            chunk = self._chunks[idx]
            if not self._apply_filters(chunk, filters):
                continue
            results.append(VectorSearchResult(chunk=chunk, score=float(scores[idx]), retrieval_type="dense"))
            if len(results) >= top_k:
                break

        return results

    def search_sparse(
        self,
        query_text: str,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """Simple in-memory term frequency keyword search."""
        terms = [t.lower() for t in query_text.split() if len(t) > 1]
        if not terms:
            return []

        scored_chunks = []
        for chunk in self._chunks:
            if not self._apply_filters(chunk, filters):
                continue
            chunk_lower = chunk.text.lower()
            matches = sum(1 for term in terms if term in chunk_lower)
            if matches > 0:
                scored_chunks.append((chunk, float(matches) / len(terms)))

        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        return [
            VectorSearchResult(chunk=c, score=s, retrieval_type="sparse")
            for c, s in scored_chunks[:top_k]
        ]

    def search_exact_section(
        self,
        section_number: str,
        act_id: Optional[str] = None,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        en_sec = normalize_to_en_digits(section_number).strip().lower()
        results: List[VectorSearchResult] = []

        for chunk in self._chunks:
            if not self._apply_filters(chunk, filters):
                continue
            if act_id and chunk.act_id != act_id:
                continue

            chunk_sec = normalize_to_en_digits(chunk.section or "").strip().lower()
            prov_label = normalize_to_en_digits(chunk.provision_label or "").strip().lower()

            if chunk_sec == en_sec or f"section {en_sec}" in prov_label or f"ধারা {section_number}" in (chunk.provision_label or ""):
                results.append(VectorSearchResult(chunk=chunk, score=1.0, retrieval_type="exact"))
                if len(results) >= top_k:
                    break

        return results

    def get_parent_section_chunks(self, chunk: LegalChunkPayload) -> List[LegalChunkPayload]:
        """Returns all chunks belonging to the same Act and Section."""
        if not chunk.section or not chunk.act_id:
            return [chunk]

        family = [
            c for c in self._chunks
            if c.act_id == chunk.act_id and c.section == chunk.section
        ]
        family.sort(key=lambda x: x.chunk_index)
        return family if family else [chunk]

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """Backward-compatible search alias pointing to search_dense."""
        return self.search_dense(query_embedding=query_embedding, top_k=top_k, filters=filters)


class PgVectorStore(BaseVectorStore):
    """Production PostgreSQL 16 client with pgvector HNSW indexing and GIN full-text search."""

    def __init__(self, db_url: str):
        self.db_url = db_url

    def _execute_session_tuning(self, cur):
        """Applies pgvector 0.8+ query-time settings if supported."""
        try:
            cur.execute("SET LOCAL hnsw.ef_search = 100;")
            cur.execute("SET LOCAL hnsw.iterative_scan = strict_order;")
            cur.execute("SET LOCAL hnsw.max_scan_tuples = 20000;")
            cur.execute("SET LOCAL hnsw.scan_mem_multiplier = 2;")
        except Exception:
            # Silently pass if running on a test engine without specific config knobs
            pass

    def add_chunks(self, chunks: List[LegalChunkPayload], embeddings: List[List[float]]) -> int:
        import psycopg

        if len(chunks) != len(embeddings):
            raise ValueError("Chunks count must match embeddings count")

        inserted = 0
        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                for chunk, emb in zip(chunks, embeddings):
                    vec_str = "[" + ",".join(str(x) for x in emb) + "]"
                    cur.execute(
                        """
                        INSERT INTO legal_chunks (
                            id, legal_source_id, act_id, act_name, act_name_bn, act_year,
                            chapter, section, subsection, clause, language, jurisdiction,
                            parent_id, effective_from, effective_to, is_current, source_page,
                            document_version, provision_label, chunk_index, text, token_count,
                            source_url, content_hash, embedding, embedding_model, embedding_version,
                            is_active, metadata
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s::vector, %s, %s,
                            %s, %s::jsonb
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            text = EXCLUDED.text,
                            embedding = EXCLUDED.embedding,
                            is_current = EXCLUDED.is_current,
                            is_active = EXCLUDED.is_active;
                        """,
                        (
                            str(chunk.id),
                            str(chunk.legal_source_id) if chunk.legal_source_id else None,
                            chunk.act_id or "",
                            chunk.act_name,
                            chunk.act_name_bn,
                            chunk.act_year,
                            chunk.chapter,
                            chunk.section,
                            chunk.subsection,
                            chunk.clause,
                            chunk.language.value,
                            chunk.jurisdiction,
                            str(chunk.parent_id) if chunk.parent_id else None,
                            chunk.effective_from,
                            chunk.effective_to,
                            chunk.is_current,
                            chunk.source_page,
                            chunk.document_version,
                            chunk.provision_label,
                            chunk.chunk_index,
                            chunk.text,
                            chunk.token_count,
                            chunk.source_url,
                            chunk.content_hash,
                            vec_str,
                            chunk.metadata.get("embedding_model", "intfloat/multilingual-e5-large"),
                            chunk.document_version,
                            True,
                            json.dumps(chunk.metadata),
                        ),
                    )
                    inserted += 1
            conn.commit()
        return inserted

    def _row_to_payload(self, row) -> LegalChunkPayload:
        return LegalChunkPayload(
            id=row[0],
            legal_source_id=row[1],
            act_id=row[2],
            act_name=row[3],
            act_name_bn=row[4],
            act_year=row[5],
            chapter=row[6],
            section=row[7],
            subsection=row[8],
            clause=row[9],
            language=LegalLanguage(row[10]),
            jurisdiction=row[11],
            parent_id=row[12],
            effective_from=row[13],
            effective_to=row[14],
            is_current=row[15],
            source_page=row[16],
            document_version=row[17],
            provision_label=row[18],
            chunk_index=row[19],
            text=row[20],
            token_count=row[21],
            source_url=row[22],
            content_hash=row[23],
            metadata=row[24] if isinstance(row[24], dict) else {},
        )

    def search_dense(
        self,
        query_embedding: List[float],
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        import psycopg

        vec_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        where_clauses = ["is_active = true"]
        params: List[Any] = [vec_str]

        # Amendment / version awareness default: return current unless requested
        if filters and "is_current" in filters:
            where_clauses.append("is_current = %s")
            params.append(filters["is_current"])
        else:
            where_clauses.append("is_current = true")

        if filters and "act_id" in filters:
            where_clauses.append("act_id = %s")
            params.append(filters["act_id"])

        where_sql = " AND ".join(where_clauses)
        params.extend([vec_str, top_k])

        query = f"""
            SELECT id, legal_source_id, act_id, act_name, act_name_bn, act_year,
                   chapter, section, subsection, clause, language, jurisdiction,
                   parent_id, effective_from, effective_to, is_current, source_page,
                   document_version, provision_label, chunk_index, text, token_count,
                   source_url, content_hash, metadata,
                   1 - (embedding <=> %s::vector) AS cosine_similarity
            FROM legal_chunks
            WHERE {where_sql}
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """

        results: List[VectorSearchResult] = []
        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                self._execute_session_tuning(cur)
                cur.execute(query, params)
                for row in cur.fetchall():
                    chunk = self._row_to_payload(row[:-1])
                    sim = float(row[-1])
                    results.append(VectorSearchResult(chunk=chunk, score=sim, retrieval_type="dense"))
        return results

    def search_sparse(
        self,
        query_text: str,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        import psycopg

        # Clean query for plainto_tsquery
        clean_query = query_text.replace("'", " ").strip()
        if not clean_query:
            return []

        where_clauses = ["is_active = true", "tsv @@ plainto_tsquery('simple', %s)"]
        params: List[Any] = [clean_query]

        if filters and "is_current" in filters:
            where_clauses.append("is_current = %s")
            params.append(filters["is_current"])
        else:
            where_clauses.append("is_current = true")

        if filters and "act_id" in filters:
            where_clauses.append("act_id = %s")
            params.append(filters["act_id"])

        where_sql = " AND ".join(where_clauses)
        params.extend([clean_query, top_k])

        query = f"""
            SELECT id, legal_source_id, act_id, act_name, act_name_bn, act_year,
                   chapter, section, subsection, clause, language, jurisdiction,
                   parent_id, effective_from, effective_to, is_current, source_page,
                   document_version, provision_label, chunk_index, text, token_count,
                   source_url, content_hash, metadata,
                   ts_rank_cd(tsv, plainto_tsquery('simple', %s)) AS rank_score
            FROM legal_chunks
            WHERE {where_sql}
            ORDER BY rank_score DESC
            LIMIT %s;
        """

        results: List[VectorSearchResult] = []
        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                for row in cur.fetchall():
                    chunk = self._row_to_payload(row[:-1])
                    score = float(row[-1])
                    results.append(VectorSearchResult(chunk=chunk, score=score, retrieval_type="sparse"))
        return results

    def search_exact_section(
        self,
        section_number: str,
        act_id: Optional[str] = None,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        import psycopg

        en_num = normalize_to_en_digits(section_number).strip().lower()
        where_clauses = [
            "is_active = true",
            "(lower(section) = %s OR lower(provision_label) LIKE %s)",
        ]
        params: List[Any] = [en_num, f"%section {en_num}%"]

        if act_id:
            where_clauses.append("act_id = %s")
            params.append(act_id)

        if filters and "is_current" in filters:
            where_clauses.append("is_current = %s")
            params.append(filters["is_current"])
        else:
            where_clauses.append("is_current = true")

        where_sql = " AND ".join(where_clauses)
        params.append(top_k)

        query = f"""
            SELECT id, legal_source_id, act_id, act_name, act_name_bn, act_year,
                   chapter, section, subsection, clause, language, jurisdiction,
                   parent_id, effective_from, effective_to, is_current, source_page,
                   document_version, provision_label, chunk_index, text, token_count,
                   source_url, content_hash, metadata
            FROM legal_chunks
            WHERE {where_sql}
            ORDER BY chunk_index ASC
            LIMIT %s;
        """

        results: List[VectorSearchResult] = []
        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                for row in cur.fetchall():
                    chunk = self._row_to_payload(row)
                    results.append(VectorSearchResult(chunk=chunk, score=1.0, retrieval_type="exact"))
        return results

    def get_parent_section_chunks(self, chunk: LegalChunkPayload) -> List[LegalChunkPayload]:
        import psycopg

        if not chunk.act_id or not chunk.section:
            return [chunk]

        query = """
            SELECT id, legal_source_id, act_id, act_name, act_name_bn, act_year,
                   chapter, section, subsection, clause, language, jurisdiction,
                   parent_id, effective_from, effective_to, is_current, source_page,
                   document_version, provision_label, chunk_index, text, token_count,
                   source_url, content_hash, metadata
            FROM legal_chunks
            WHERE act_id = %s AND section = %s AND is_active = true
            ORDER BY chunk_index ASC;
        """

        family: List[LegalChunkPayload] = []
        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (chunk.act_id, chunk.section))
                for row in cur.fetchall():
                    family.append(self._row_to_payload(row))

        return family if family else [chunk]

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        return self.search_dense(query_embedding=query_embedding, top_k=top_k, filters=filters)
