-- Replace the legal knowledge base in Neon with the full e5-small corpus.
-- Run only through deploy/neon_cutover_e5small.sh (it sets the psql variables, mounts
-- the exported files at /corpus and passes the psql variables). One transaction: it
-- ends in COMMIT, or ROLLBACK when dry_run is on.
--
-- Touches public.legal_sources, legal_source_versions, legal_sections, legal_chunks,
-- one reviewer row in public.users (only if that account does not exist yet) and the
-- approval audit events. Every other table is checked to be unchanged.
-- Any failed check raises: psql stops (ON_ERROR_STOP) and the transaction rolls back.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL statement_timeout = 0;
SELECT set_config('cutover.reviewer_email', :'reviewer_email', true),
       set_config('cutover.reviewer_name', :'reviewer_name', true),
       set_config('cutover.note', :'note', true),
       set_config('cutover.n_sources', :'n_sources', true),
       set_config('cutover.n_versions', :'n_versions', true),
       set_config('cutover.n_sections', :'n_sections', true),
       set_config('cutover.n_chunks', :'n_chunks', true),
       set_config('cutover.stage_sources', :'sources_cols', true),
       set_config('cutover.stage_versions', :'versions_cols', true),
       set_config('cutover.stage_sections', :'sections_cols', true),
       set_config('cutover.stage_chunks', :'chunks_cols', true) \g /dev/null
SET LOCAL maintenance_work_mem = '128MB';
SET LOCAL max_parallel_maintenance_workers = 0;  -- serial HNSW build: no large shared-memory segment

-- 0. Preconditions ---------------------------------------------------------------------
DO $$
BEGIN
  IF current_user <> 'app_owner' THEN
    RAISE EXCEPTION 'connect as app_owner, not %', current_user;
  END IF;
  IF (SELECT version_num FROM public.alembic_version) <> '0022_query_rewrite_cache' THEN
    RAISE EXCEPTION 'run alembic upgrade head (0022_query_rewrite_cache) first; database is at %',
      (SELECT version_num FROM public.alembic_version);
  END IF;
END $$;

-- Row counts of every other table, to prove they are untouched.
CREATE TEMP TABLE cutover_before ON COMMIT DROP AS
SELECT c.relname,
       (xpath('/row/n/text()', query_to_xml(format('SELECT count(*) AS n FROM public.%I', c.relname),
                                            false, true, '')))[1]::text::bigint AS n
FROM pg_class c
WHERE c.relnamespace = 'public'::regnamespace AND c.relkind = 'r' AND c.relname NOT LIKE 'legal\_%';

-- Chunk ids that saved analyses and strategy trees cite (kept below where the text is unchanged).
CREATE TEMP TABLE cutover_cited ON COMMIT DROP AS
SELECT DISTINCT (v #>> '{}')::uuid AS chunk_id
FROM (
  SELECT jsonb_path_query(result, 'lax $.**.chunk_id') AS v FROM public.case_analyses
  UNION ALL
  SELECT jsonb_path_query(tree, 'lax $.**.chunk_id') FROM public.strategy_trees
) cited
WHERE jsonb_typeof(v) = 'string' AND (v #>> '{}') ~ '^[0-9a-f-]{36}$';

-- 1. Reviewer: the named account; created as an active admin only if it does not exist --
DO $$
DECLARE
  v_status text;
  v_role text;
BEGIN
  SELECT status, role INTO v_status, v_role FROM public.users WHERE email = current_setting('cutover.reviewer_email')::citext;
  IF NOT FOUND THEN
    IF coalesce(current_setting('cutover.reviewer_name'), '') = '' THEN
      RAISE EXCEPTION 'reviewer % does not exist in this database; set REVIEWER_NAME to create it',
        current_setting('cutover.reviewer_email');
    END IF;
    INSERT INTO public.users (email, role, status, full_name)
    VALUES (current_setting('cutover.reviewer_email'), 'admin', 'active', current_setting('cutover.reviewer_name'));
    RAISE NOTICE 'created reviewer account (active admin, no password yet)';
  ELSIF v_status <> 'active' OR v_role NOT IN ('lawyer', 'admin') THEN
    RAISE EXCEPTION 'reviewer exists but is % %; it must be an active lawyer or admin', v_status, v_role;
  ELSE
    RAISE NOTICE 'reviewer account exists (% %)', v_status, v_role;
  END IF;
END $$;

-- 2. Stage the new corpus (temp tables: no RLS, so COPY is allowed) -------------------------
CREATE TEMP TABLE stage_sources (LIKE public.legal_sources) ON COMMIT DROP;
CREATE TEMP TABLE stage_versions (LIKE public.legal_source_versions) ON COMMIT DROP;
CREATE TEMP TABLE stage_sections (LIKE public.legal_sections) ON COMMIT DROP;
CREATE TEMP TABLE stage_chunks (LIKE public.legal_chunks) ON COMMIT DROP;
ALTER TABLE stage_chunks DROP COLUMN tsv;

-- The files hold these columns in this order (manifest.json); the staging tables must match.
DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['stage_sources', 'stage_versions', 'stage_sections', 'stage_chunks'] LOOP
    IF (SELECT string_agg(attname, ',' ORDER BY attnum) FROM pg_attribute
        WHERE attrelid = t::regclass AND attnum > 0 AND NOT attisdropped) <> current_setting('cutover.' || t) THEN
      RAISE EXCEPTION '% columns differ from the exported file columns', t;
    END IF;
  END LOOP;
END $$;

\copy stage_sources FROM '/corpus/legal_sources.tsv'
\copy stage_versions FROM '/corpus/legal_source_versions.tsv'
\copy stage_sections FROM '/corpus/legal_sections.tsv'
\copy stage_chunks FROM '/corpus/legal_chunks.tsv'

DO $$
BEGIN
  IF (SELECT count(*) FROM stage_sources) <> current_setting('cutover.n_sources')::int
     OR (SELECT count(*) FROM stage_versions) <> current_setting('cutover.n_versions')::int
     OR (SELECT count(*) FROM stage_sections) <> current_setting('cutover.n_sections')::int
     OR (SELECT count(*) FROM stage_chunks) <> current_setting('cutover.n_chunks')::int THEN
    RAISE EXCEPTION 'staged row counts do not match manifest.json';
  END IF;
  IF EXISTS (SELECT 1 FROM stage_chunks WHERE is_active AND (embedding IS NULL OR vector_dims(embedding) <> 384
             OR embedding_model <> 'intfloat/multilingual-e5-small' OR embedding_version <> 1)) THEN
    RAISE EXCEPTION 'staged chunks are not all e5-small v1 (384 dims)';
  END IF;
  IF EXISTS (SELECT 1 FROM stage_versions WHERE review_status <> 'pending' OR reviewed_by IS NOT NULL) THEN
    RAISE EXCEPTION 'staged versions must be pending with no reviewer';
  END IF;
END $$;

-- 3. Keep existing ids where the same Act/version/section/chunk text is already here ----------
-- Saved analyses cite chunk ids; a chunk keeps its id only if its text is identical.
CREATE TEMP TABLE map_sources ON COMMIT DROP AS
SELECT n.id AS new_id, o.id AS old_id FROM stage_sources n
JOIN public.legal_sources o USING (source_name, external_id, language);
UPDATE stage_versions v SET legal_source_id = m.old_id FROM map_sources m WHERE v.legal_source_id = m.new_id;
UPDATE stage_sources s SET id = m.old_id FROM map_sources m WHERE s.id = m.new_id;

CREATE TEMP TABLE map_versions ON COMMIT DROP AS
SELECT n.id AS new_id, o.id AS old_id FROM stage_versions n
JOIN public.legal_source_versions o USING (legal_source_id, version_no);
UPDATE stage_sections s SET legal_source_version_id = m.old_id FROM map_versions m WHERE s.legal_source_version_id = m.new_id;
UPDATE stage_chunks c SET legal_source_version_id = m.old_id FROM map_versions m WHERE c.legal_source_version_id = m.new_id;
UPDATE stage_versions v SET id = m.old_id FROM map_versions m WHERE v.id = m.new_id;

CREATE TEMP TABLE map_sections ON COMMIT DROP AS
SELECT n.id AS new_id, o.id AS old_id FROM stage_sections n
JOIN public.legal_sections o USING (legal_source_version_id, section_key);
UPDATE stage_chunks c SET legal_section_id = m.old_id FROM map_sections m WHERE c.legal_section_id = m.new_id;
UPDATE stage_sections s SET id = m.old_id FROM map_sections m WHERE s.id = m.new_id;

CREATE TEMP TABLE map_chunks ON COMMIT DROP AS
SELECT n.id AS new_id, o.id AS old_id FROM stage_chunks n
JOIN public.legal_chunks o USING (legal_section_id, chunk_index, content_hash);
UPDATE stage_chunks c SET id = m.old_id FROM map_chunks m WHERE c.id = m.new_id;

SELECT (SELECT count(*) FROM map_sources) AS kept_source_ids,
       (SELECT count(*) FROM map_versions) AS kept_version_ids,
       (SELECT count(*) FROM map_sections) AS kept_section_ids,
       (SELECT count(*) FROM map_chunks) AS kept_chunk_ids,
       (SELECT count(*) FROM cutover_cited) AS cited_chunk_ids,
       (SELECT count(*) FROM cutover_cited c WHERE c.chunk_id IN (SELECT id FROM stage_chunks)) AS cited_still_present;

-- 4. Replace the data (HNSW index rebuilt once at the end) ------------------------------------
-- TRUNCATE (not DELETE): new empty files inside this transaction. COMMIT frees the old
-- files and ROLLBACK discards the new ones, so neither a dry run nor a re-run leaves dead
-- rows behind (Neon free plan: 0.5 GB). Search waits on the table lock until COMMIT.
TRUNCATE public.legal_chunks, public.legal_sections, public.legal_source_versions, public.legal_sources;

DROP INDEX public.ix_legal_chunks_embedding_hnsw_384;

INSERT INTO public.legal_sources SELECT * FROM stage_sources;
INSERT INTO public.legal_source_versions SELECT * FROM stage_versions;
INSERT INTO public.legal_sections SELECT * FROM stage_sections ORDER BY legal_source_version_id, position;
INSERT INTO public.legal_chunks (id, legal_source_version_id, legal_section_id, provision_label, chunk_index, text,
                                 token_count, content_hash, embedding, embedding_model, embedding_version,
                                 embedded_at, is_active, created_at)
SELECT id, legal_source_version_id, legal_section_id, provision_label, chunk_index, text, token_count,
       content_hash, embedding, embedding_model, embedding_version, embedded_at, is_active, created_at
FROM stage_chunks ORDER BY legal_section_id, chunk_index;

-- Same definition as migration 0021.
CREATE INDEX ix_legal_chunks_embedding_hnsw_384 ON public.legal_chunks
  USING hnsw ((embedding::vector(384)) vector_cosine_ops) WHERE vector_dims(embedding) = 384;

-- 5. Approve every version under the reviewer (writes Neon audit events) ---------------------
DO $$
DECLARE
  v uuid;
BEGIN
  FOR v IN SELECT id FROM public.legal_source_versions WHERE review_status = 'pending' ORDER BY id LOOP
    PERFORM app.approve_legal_source_version(v, current_setting('cutover.reviewer_email'),
                                             current_setting('cutover.note'));
  END LOOP;
END $$;

-- 6. Verify ---------------------------------------------------------------------------------
DO $$
DECLARE
  r record;
  n bigint;
  v_reviewer uuid := app.find_legal_reviewer(current_setting('cutover.reviewer_email'));
BEGIN
  IF (SELECT count(*) FROM public.legal_sources) <> current_setting('cutover.n_sources')::int
     OR (SELECT count(*) FROM public.legal_source_versions) <> current_setting('cutover.n_versions')::int
     OR (SELECT count(*) FROM public.legal_sections) <> current_setting('cutover.n_sections')::int
     OR (SELECT count(*) FROM public.legal_chunks) <> current_setting('cutover.n_chunks')::int THEN
    RAISE EXCEPTION 'loaded row counts do not match manifest.json';
  END IF;
  IF EXISTS (SELECT 1 FROM public.legal_source_versions
             WHERE review_status <> 'approved' OR reviewed_by IS DISTINCT FROM v_reviewer) THEN
    RAISE EXCEPTION 'not every version is approved by the reviewer';
  END IF;
  IF EXISTS (SELECT 1 FROM public.legal_chunks WHERE is_active AND (vector_dims(embedding) <> 384
             OR embedding_model <> 'intfloat/multilingual-e5-small' OR embedding_version <> 1)) THEN
    RAISE EXCEPTION 'loaded chunks are not all e5-small v1';
  END IF;
  IF EXISTS (SELECT 1 FROM public.legal_chunks WHERE tsv IS NULL) THEN
    RAISE EXCEPTION 'keyword index column tsv is empty';
  END IF;
  FOR r IN SELECT * FROM cutover_before LOOP
    EXECUTE format('SELECT count(*) FROM public.%I', r.relname) INTO n;
    IF r.relname = 'audit_logs' THEN
      IF n - r.n <> current_setting('cutover.n_versions')::int THEN
        RAISE EXCEPTION 'audit_logs grew by %, expected one approval event per version', n - r.n;
      END IF;
    ELSIF r.relname = 'users' THEN
      IF n - r.n NOT IN (0, 1) THEN RAISE EXCEPTION 'users changed by %', n - r.n; END IF;
    ELSIF n <> r.n THEN
      RAISE EXCEPTION 'table % changed (% -> % rows); it must not be touched', r.relname, r.n, n;
    END IF;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_class WHERE relnamespace = 'public'::regnamespace AND relkind = 'r'
             AND relname <> 'alembic_version' AND NOT (relrowsecurity AND relforcerowsecurity)) THEN
    RAISE EXCEPTION 'row level security is not enabled and forced on every table';
  END IF;
END $$;

SELECT (SELECT count(*) FROM public.legal_source_versions WHERE review_status = 'approved') AS approved_acts,
       (SELECT count(*) FROM public.legal_sections) AS sections,
       (SELECT count(*) FROM public.legal_chunks) AS chunks,
       (SELECT count(*) FROM cutover_cited c WHERE NOT EXISTS (SELECT 1 FROM public.legal_chunks x WHERE x.id = c.chunk_id))
         AS cited_chunks_no_longer_present,
       (SELECT count(*) FILTER (WHERE relforcerowsecurity) || '/' || count(*) FROM pg_class
        WHERE relnamespace = 'public'::regnamespace AND relkind = 'r' AND relrowsecurity) AS rls_forced;

\if :dry_run
  \echo '[cutover] DRY RUN: every check passed; rolling back, nothing changed'
  ROLLBACK;
\else
  COMMIT;
  \echo '[cutover] COMMITTED'
\endif
