"""SQL Schema and Migration definitions for Legal Knowledge Base.

Includes:
1. legal_sources table
2. legal_source_versions table
3. legal_chunks table with:
   - VECTOR(1024)
   - Full-text search vector (tsv) with weighted ranking (Act: A, Title/Section: A, Body: B)
   - Amendment & version aware metadata fields
   - HNSW index configuration (m=24, ef_construction=128)
   - GIN index on full-text search vector
   - B-tree indexes on exact section, act_id, and amendment status
"""

CREATE_LEGAL_KB_TABLES_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS legal_sources (
    id UUID PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('constitution','act','ordinance','code','rule','regulation','notification','judgment','other')),
    title TEXT NOT NULL,
    title_bn TEXT,
    short_title TEXT,
    citation TEXT,
    number_year TEXT,
    language TEXT NOT NULL CHECK (language IN ('bn','en','both')),
    current_status TEXT NOT NULL DEFAULT 'in_force' CHECK (current_status IN ('in_force','amended','repealed','partly_repealed','unknown')),
    effective_from DATE,
    effective_to DATE,
    source_url TEXT,
    source_name TEXT NOT NULL,
    licence_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_legal_sources_status ON legal_sources(current_status);
CREATE INDEX IF NOT EXISTS idx_legal_sources_title_trgm ON legal_sources USING gin (title gin_trgm_ops);

CREATE TABLE IF NOT EXISTS legal_chunks (
    id UUID PRIMARY KEY,
    legal_source_id UUID REFERENCES legal_sources(id) ON DELETE SET NULL,
    act_id TEXT NOT NULL,
    act_name TEXT NOT NULL,
    act_name_bn TEXT,
    act_year TEXT,
    chapter TEXT,
    section TEXT,
    subsection TEXT,
    clause TEXT,
    language TEXT NOT NULL CHECK (language IN ('bn','en','both')),
    jurisdiction TEXT NOT NULL DEFAULT 'Bangladesh',
    parent_id UUID,
    effective_from DATE,
    effective_to DATE,
    is_current BOOLEAN NOT NULL DEFAULT true,
    source_page INT,
    document_version INT NOT NULL DEFAULT 1,
    provision_label TEXT,
    chunk_index INT NOT NULL,
    text TEXT NOT NULL,
    token_count INT NOT NULL,
    source_url TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    embedding VECTOR(1024),
    embedding_model TEXT NOT NULL DEFAULT 'intfloat/multilingual-e5-large',
    embedding_version INT NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT true,
    tsv TSVECTOR,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Full-Text Search TSVECTOR Generation Trigger / Function with Weighted Ranking:
-- Act name & Bengali Act name: 'A'
-- Provision label / Section number: 'A'
-- Legal provision text body: 'B'
CREATE OR REPLACE FUNCTION legal_chunks_tsv_update() RETURNS trigger AS $$
BEGIN
    NEW.tsv := 
        setweight(to_tsvector('simple', coalesce(NEW.act_name, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(NEW.act_name_bn, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(NEW.provision_label, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(NEW.section, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(NEW.text, '')), 'B');
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_legal_chunks_tsv_update ON legal_chunks;
CREATE TRIGGER trg_legal_chunks_tsv_update
BEFORE INSERT OR UPDATE ON legal_chunks
FOR EACH ROW EXECUTE FUNCTION legal_chunks_tsv_update();

-- HNSW Cosine Index with m=24 and ef_construction=128
CREATE INDEX IF NOT EXISTS legal_chunks_embedding_hnsw
ON legal_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 24, ef_construction = 128);

-- GIN Index on weighted full-text search vector
CREATE INDEX IF NOT EXISTS idx_legal_chunks_tsv
ON legal_chunks
USING gin (tsv);

-- B-Tree and Filter Indexes
CREATE INDEX IF NOT EXISTS idx_legal_chunks_act_section
ON legal_chunks (act_id, section);

CREATE INDEX IF NOT EXISTS idx_legal_chunks_section_lower
ON legal_chunks (lower(section));

CREATE INDEX IF NOT EXISTS idx_legal_chunks_is_current
ON legal_chunks (is_current, is_active);

CREATE INDEX IF NOT EXISTS idx_legal_chunks_parent_id
ON legal_chunks (parent_id);
"""
