"""FastAPI application server for Legal-Copilot backend.

Provides:
- Health check
- Interactive OpenAPI documentation (/docs, /redoc)
- Hybrid RAG Legal Search API (/api/v1/legal-kb/search)
- Exact Section Lookup API (/api/v1/legal-kb/section)
- Document Upload & Validation API (/api/v1/documents/process)
"""

import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Load backend/.env if present
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env")))

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.src.analysis.router import router as analysis_router
from backend.src.documents.pipeline import DocumentProcessingPipeline
from backend.src.hearings.router import router as hearings_router
from backend.src.strategy.router import router as strategy_router
from backend.src.legal_kb.embeddings import MockEmbeddingProvider
from backend.src.legal_kb.retriever import LegalHybridRetriever
from backend.src.legal_kb.schemas import LegalChunkPayload
from backend.src.legal_kb.vector_store import PgVectorStore, VectorSearchResult

app = FastAPI(
    title="AI Legal Copilot for Bangladesh",
    version="1.0.0",
    description="Legal Decision-Support API with Hybrid RAG & Document Processing.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database & Retriever Setup
# No credential fallback: set DATABASE_URL in the environment.
DB_URL = os.environ.get("DATABASE_URL", "")
vector_store = PgVectorStore(db_url=DB_URL)
embedding_provider = MockEmbeddingProvider(dimension=1024)
retriever = LegalHybridRetriever(
    vector_store=vector_store,
    embedding_provider=embedding_provider,
    rrf_k=60,
)
doc_pipeline = DocumentProcessingPipeline()


class SearchResponseItem(BaseModel):
    chunk_id: str
    act_name: str
    act_year: Optional[str] = None
    section: Optional[str] = None
    provision_label: Optional[str] = None
    score: float
    retrieval_type: str
    text: str
    source_url: str


class SearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[SearchResponseItem]


app.include_router(analysis_router, prefix="/api/v1")
app.include_router(strategy_router, prefix="/api/v1")
app.include_router(hearings_router, prefix="/api/v1")


@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "legal-copilot-backend"}


@app.get(
    "/api/v1/legal-kb/search",
    response_model=SearchResponse,
    summary="Hybrid Legal Search",
    tags=["Legal Knowledge Base"],
)
def search_legal_knowledge(
    q: str = Query(..., description="Legal question or keywords in English or Bengali (e.g. 'খুনের শাস্তি' or 'Section 302')"),
    top_k: int = Query(5, ge=1, le=20, description="Number of legal provisions to return"),
    act_id: Optional[str] = Query(None, description="Optional Act ID filter"),
):
    """Executes multi-stage hybrid retrieval:

    1. Exact section number lookup (Bangla & English numerals)
    2. Full-Text Search (weighted TSVECTOR)
    3. Dense vector cosine search (pgvector 1024-dim)
    4. Reciprocal Rank Fusion (RRF)
    5. Complete Parent-section expansion
    """
    filters = {"act_id": act_id} if act_id else None
    results = retriever.retrieve(
        query=q,
        dense_k=20,
        sparse_k=20,
        rerank_top_k=top_k,
        filters=filters,
        expand_parent_sections=True,
    )

    items = [
        SearchResponseItem(
            chunk_id=str(r.chunk.id),
            act_name=r.chunk.act_name,
            act_year=r.chunk.act_year,
            section=r.chunk.section,
            provision_label=r.chunk.provision_label,
            score=round(r.score, 4),
            retrieval_type=r.retrieval_type,
            text=r.chunk.text,
            source_url=r.chunk.source_url,
        )
        for r in results
    ]

    return SearchResponse(query=q, total_results=len(items), results=items)


@app.post(
    "/api/v1/documents/process",
    summary="Validate and Process Case Document",
    tags=["Documents"],
)
async def process_document(file: UploadFile = File(...)):
    """Uploads, validates magic bytes, extracts pages, and creates case chunks."""
    content = await file.read()
    try:
        from uuid import uuid4

        case_id = uuid4()
        meta, pages, chunks = doc_pipeline.process_document(
            file_bytes=content,
            filename=file.filename or "uploaded_doc",
            case_id=case_id,
        )
        return {
            "document_id": str(meta.id),
            "status": meta.status,
            "mime_type": meta.mime_type,
            "total_pages": meta.total_pages,
            "total_chunks": len(chunks),
            "pages_preview": [
                {
                    "page_number": p.page_number,
                    "language": p.language,
                    "quality_flag": p.quality_flag,
                    "text_preview": p.text[:150] + "..." if len(p.text) > 150 else p.text,
                }
                for p in pages[:5]
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
