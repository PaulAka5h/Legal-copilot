#!/usr/bin/env bash
# Replace Neon's legal knowledge base with the full e5-small corpus (data only).
#
#   deploy/export_legal_corpus.sh                       # once, locally -> deploy/corpus_e5small/
#   export NEON_APP_OWNER_URL='postgresql://app_owner:<pw>@<direct host>/neondb?sslmode=require'
#   REVIEWER_EMAIL=you@example.com DRY_RUN=1 deploy/neon_cutover_e5small.sh   # everything, then ROLLBACK
#   REVIEWER_EMAIL=you@example.com DRY_RUN=0 deploy/neon_cutover_e5small.sh   # the real run
#
# Optional: REVIEWER_NAME (only used, and then required, if REVIEWER_EMAIL has no account:
# it is created as an active admin without a password), NOTE (approval note),
# CORPUS_DIR (default deploy/corpus_e5small).
#
# Prerequisite: migrations through 0022 applied as app_owner (alembic upgrade head).
# What it does, in ONE transaction (deploy/neon_cutover_e5small.sql): stage the files in
# temp tables, keep existing ids where the text is identical (saved analyses cite chunk
# ids), replace the four legal_* tables, rebuild the 384-dim HNSW index, approve every
# version under REVIEWER_EMAIL (Neon audit events), verify counts, vectors, that no
# other table changed and that RLS is forced on every table; then COMMIT (or ROLLBACK
# with DRY_RUN=1). Any failure rolls everything back.
# Runs psql from a postgres:17 Docker image; the URL goes in as an environment variable,
# never as an argument.
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORPUS_DIR="$(cd "${CORPUS_DIR:-$HERE/corpus_e5small}" && pwd)"
CLIENT_IMAGE="${CLIENT_IMAGE:-postgres:17}"
DRY_RUN="${DRY_RUN:-1}"
NOTE="${NOTE:-Bulk bdlaws import; spot-checked 5 Acts (138, 952, 180, 1054, 1124) against source; not individually reviewed by a lawyer}"

die() { printf '[cutover] ERROR: %s\n' "$*" >&2; exit 1; }
log() { printf '[cutover] %s\n' "$*"; }

: "${NEON_APP_OWNER_URL:?Set NEON_APP_OWNER_URL=postgresql://app_owner:...@<direct host>/neondb?sslmode=require}"
: "${REVIEWER_EMAIL:?Set REVIEWER_EMAIL to the Neon account that approves the corpus}"
[[ "$NEON_APP_OWNER_URL" == postgresql://app_owner:* ]] || die "connect as app_owner (postgresql://app_owner:...)"
[[ "$NEON_APP_OWNER_URL" != *-pooler.* ]] || die "use the direct host, not the -pooler host"
[[ "$DRY_RUN" == 0 || "$DRY_RUN" == 1 ]] || die "DRY_RUN must be 0 or 1"
[[ -s "$CORPUS_DIR/manifest.json" ]] || die "$CORPUS_DIR/manifest.json not found; run deploy/export_legal_corpus.sh"

# Check the files against the manifest and read the counts and column lists.
eval "$(python3 - "$CORPUS_DIR" <<'PY'
import hashlib, json, shlex, sys
from pathlib import Path
root = Path(sys.argv[1])
m = json.loads((root / "manifest.json").read_text())
if m["embedding"] != {"model": "intfloat/multilingual-e5-small", "version": 1, "dimension": 384}:
    sys.exit("[cutover] ERROR: manifest is not an e5-small v1 corpus")
short = {"legal_sources": "sources", "legal_source_versions": "versions", "legal_sections": "sections",
         "legal_chunks": "chunks"}
for table, key in short.items():
    t = m["tables"][table]
    if hashlib.sha256((root / t["file"]).read_bytes()).hexdigest() != t["sha256"]:
        sys.exit(f"[cutover] ERROR: {t['file']} does not match its SHA-256 in manifest.json")
    print(f"N_{key.upper()}={t['rows']}")
    print(f"COLS_{key.upper()}={shlex.quote(t['columns'].replace(' ', ''))}")
PY
)"
log "Corpus: $N_SOURCES sources, $N_VERSIONS versions, $N_SECTIONS sections, $N_CHUNKS chunks (files verified)"

psql_run() {
  docker run --rm -i --network host -e PGURL="$NEON_APP_OWNER_URL" -v "$CORPUS_DIR:/corpus:ro" \
    -v "$HERE/neon_cutover_e5small.sql:/cutover.sql:ro" "$CLIENT_IMAGE" "$@"
}

# The load TRUNCATEs, so it leaves no dead rows; VACUUM (ANALYZE) refreshes statistics and
# trims anything left over. Runs after every attempt, including a failed one.
vacuum_legal() {
  psql_run sh -c 'psql -X -q -v ON_ERROR_STOP=1 "$PGURL" -c "VACUUM (ANALYZE) public.legal_chunks,
    public.legal_sections, public.legal_source_versions, public.legal_sources"' \
    || log "WARNING: VACUUM failed; run it by hand: VACUUM (ANALYZE) public.legal_chunks, public.legal_sections"
  log "Database size now: $(psql_run sh -c 'psql -X -tAq "$PGURL" -c "SELECT pg_size_pretty(pg_database_size(current_database()))"')"
}

[[ "$DRY_RUN" == 1 ]] && log "DRY RUN: the transaction is rolled back at the end" \
                      || log "REAL RUN: the transaction commits if every check passes"
psql_run sh -c 'psql -X -q "$PGURL" -v ON_ERROR_STOP=1 -v dry_run="$1" -v reviewer_email="$2" \
    -v reviewer_name="$3" -v note="$4" -v n_sources="$5" -v n_versions="$6" -v n_sections="$7" \
    -v n_chunks="$8" -v sources_cols="$9" -v versions_cols="${10}" -v sections_cols="${11}" \
    -v chunks_cols="${12}" -f /cutover.sql' _ \
  "$DRY_RUN" "$REVIEWER_EMAIL" "${REVIEWER_NAME:-}" "$NOTE" "$N_SOURCES" "$N_VERSIONS" "$N_SECTIONS" \
  "$N_CHUNKS" "$COLS_SOURCES" "$COLS_VERSIONS" "$COLS_SECTIONS" "$COLS_CHUNKS" \
  || { vacuum_legal; die "cutover failed; the transaction was rolled back and nothing changed"; }
vacuum_legal
