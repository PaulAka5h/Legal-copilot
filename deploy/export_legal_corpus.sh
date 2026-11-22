#!/usr/bin/env bash
# Export the public legal knowledge base for deploy/neon_cutover_e5small.sh.
#
#   SOURCE_DB=legal_copilot_full deploy/export_legal_corpus.sh [OUT_DIR]
#
# Reads the local Compose database (superuser, read-only queries) and writes, in OUT_DIR
# (default deploy/corpus_e5small, git-ignored):
#   legal_sources.tsv, legal_source_versions.tsv, legal_sections.tsv, legal_chunks.tsv
#     (Postgres text COPY format; tsv is generated, so it is not exported)
#   manifest.json: row counts, SHA-256 of each file, the embedding label.
# Only the four legal_* tables leave this machine: no users, cases or documents.
# Versions are exported as `pending` with no reviewer: the cutover approves them in
# Neon under a Neon account, which writes Neon's own audit events.
#
# Refuses to export unless every active chunk has an e5-small v1, 384-dim vector and
# every version is approved locally (the human review step happened here).
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$REPO_ROOT/compose.yaml}"
DB_SERVICE="${DB_SERVICE:-db}"
SOURCE_DB="${SOURCE_DB:-legal_copilot_full}"
OUT="${1:-$HERE/corpus_e5small}"
MODEL="intfloat/multilingual-e5-small"

log() { printf '[export] %s\n' "$*"; }
die() { printf '[export] ERROR: %s\n' "$*" >&2; exit 1; }
dc() { docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" "$@"; }
q() { dc sh -c 'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1" -tAq -c "$2"' _ "$SOURCE_DB" "$1"; }
copy_out() { dc sh -c 'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1" -c "COPY ($2) TO STDOUT"' _ "$SOURCE_DB" "$1"; }

dc pg_isready -q >/dev/null 2>&1 || die "local database is not running; start it with: make infra-up"

[[ "$(q "SELECT count(*) FROM public.legal_chunks WHERE is_active AND (embedding IS NULL
        OR embedding_model <> '$MODEL' OR embedding_version <> 1 OR vector_dims(embedding) <> 384)")" == 0 ]] \
  || die "$SOURCE_DB has active chunks without an e5-small v1 384-dim vector; run the embed worker first"
[[ "$(q "SELECT count(*) FROM public.legal_source_versions WHERE review_status <> 'approved'")" == 0 ]] \
  || die "$SOURCE_DB has versions that are not approved; spot-check and approve them first (python -m app.rag.approve)"

mkdir -p "$OUT"
chmod 700 "$OUT"

SOURCES_COLS="id, kind, title, short_title, citation, number_year, issuing_authority, court, bench, decision_date,
  language, current_status, status_verified_on, status_note, source_url, source_name, external_id, licence_note,
  created_at"
VERSIONS_COLS="id, legal_source_id, version_no, effective_from, effective_to, full_text, content_sha256,
  amendment_note, ingested_at, ingested_by, review_status, reviewed_by, reviewed_at, is_current"
SECTIONS_COLS="id, legal_source_version_id, section_key, position, section_number, heading, chapter_number,
  chapter_title, language, text, canonical_section_id, status, status_basis, effective_from, effective_to,
  source_url, content_hash, created_at"
CHUNKS_COLS="id, legal_source_version_id, legal_section_id, provision_label, chunk_index, text, token_count,
  content_hash, embedding, embedding_model, embedding_version, embedded_at, is_active, created_at"

log "Exporting from $SOURCE_DB to $OUT"
copy_out "SELECT $SOURCES_COLS FROM public.legal_sources ORDER BY id" > "$OUT/legal_sources.tsv"
copy_out "SELECT id, legal_source_id, version_no, effective_from, effective_to, full_text, content_sha256,
  amendment_note, ingested_at, ingested_by, 'pending', NULL::uuid, NULL::timestamptz, is_current
  FROM public.legal_source_versions ORDER BY id" > "$OUT/legal_source_versions.tsv"
copy_out "SELECT $SECTIONS_COLS FROM public.legal_sections ORDER BY id" > "$OUT/legal_sections.tsv"
copy_out "SELECT $CHUNKS_COLS FROM public.legal_chunks ORDER BY id" > "$OUT/legal_chunks.tsv"

python3 - "$OUT" "$SOURCE_DB" "$MODEL" \
  "$(q "SELECT count(*) FROM public.legal_sources")" "$(q "SELECT count(*) FROM public.legal_source_versions")" \
  "$(q "SELECT count(*) FROM public.legal_sections")" "$(q "SELECT count(*) FROM public.legal_chunks")" \
  "$SOURCES_COLS" "$VERSIONS_COLS" "$SECTIONS_COLS" "$CHUNKS_COLS" <<'PY'
import hashlib, json, sys
from pathlib import Path
out, db, model, *rest = sys.argv[1:]
counts, cols = rest[:4], rest[4:]
names = ["legal_sources", "legal_source_versions", "legal_sections", "legal_chunks"]
files = {}
for name, expected, columns in zip(names, counts, cols):
    path = Path(out) / f"{name}.tsv"
    data = path.read_bytes()
    rows = data.count(b"\n")
    if rows != int(expected):
        sys.exit(f"[export] ERROR: {name}: wrote {rows} rows, expected {expected}")
    files[name] = {"file": path.name, "rows": rows, "sha256": hashlib.sha256(data).hexdigest(),
                   "columns": " ".join(columns.split())}
manifest = {"source_db": db, "embedding": {"model": model, "version": 1, "dimension": 384}, "tables": files}
(Path(out) / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v["rows"] for k, v in files.items()}))
PY
log "Done: $(du -sh "$OUT" | cut -f1) in $OUT (public statute text only; delete it after the cutover)"
