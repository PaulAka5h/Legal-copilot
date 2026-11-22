#!/usr/bin/env bash
# Back up / restore ONLY the four legal_* tables of Neon (the cutover's rollback).
#
#   export NEON_APP_OWNER_URL='postgresql://app_owner:<pw>@<direct host>/neondb?sslmode=require'
#   deploy/neon_legal_backup.sh backup             # -> deploy/backups_neon/legal_<UTC time>.sql
#   deploy/neon_legal_backup.sh restore FILE.sql   # TRUNCATE the 4 tables + load FILE, one transaction
#
# backup: pg_dump --data-only of legal_sources, legal_source_versions, legal_sections,
#   legal_chunks as INSERTs (COPY is refused where RLS applies to the writer; migration 0019),
#   with the row-security reads app_owner is allowed. Public statute text and vectors only.
# restore: puts those rows back exactly (same ids, vectors, review status). Users, cases,
#   analyses and audit events are not touched; approval audit events of the cutover stay
#   (history). Afterwards the app must use the backup's embedding model again (for the
#   pre-cutover Neon data: EMBEDDING_PROVIDER=gemini, GEMINI_EMBEDDING_MODEL=gemini-embedding-001).
# The URL reaches the postgres:17 container as an environment variable, never as an argument.
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLIENT_IMAGE="${CLIENT_IMAGE:-postgres:17}"
OUT_DIR="${OUT_DIR:-$HERE/backups_neon}"
TABLES=(legal_sources legal_source_versions legal_sections legal_chunks)

die() { printf '[legal-backup] ERROR: %s\n' "$*" >&2; exit 1; }
log() { printf '[legal-backup] %s\n' "$*"; }

: "${NEON_APP_OWNER_URL:?Set NEON_APP_OWNER_URL=postgresql://app_owner:...@<direct host>/neondb?sslmode=require}"
[[ "$NEON_APP_OWNER_URL" == postgresql://app_owner:* ]] || die "connect as app_owner (postgresql://app_owner:...)"
[[ "$NEON_APP_OWNER_URL" != *-pooler.* ]] || die "use the direct host, not the -pooler host"

pg() { docker run --rm -i --network host -e PGURL="$NEON_APP_OWNER_URL" "$@"; }
q() { pg "$CLIENT_IMAGE" sh -c 'psql -X -v ON_ERROR_STOP=1 -tAq "$PGURL" -c "$1"' _ "$1"; }
counts() { q "SELECT (SELECT count(*) FROM public.legal_source_versions) || ' versions, ' ||
  (SELECT count(*) FROM public.legal_sections) || ' sections, ' || (SELECT count(*) FROM public.legal_chunks) ||
  ' chunks (' || coalesce((SELECT string_agg(DISTINCT embedding_model || ' v' || embedding_version, ', ')
  FROM public.legal_chunks), 'no vectors') || ')'"; }

case "${1:-}" in
  backup)
    mkdir -p "$OUT_DIR"; chmod 700 "$OUT_DIR"
    file="$OUT_DIR/legal_$(date -u +%Y%m%dT%H%M%SZ).sql"
    log "Backing up: $(counts)"
    table_args=""; for t in "${TABLES[@]}"; do table_args+=" -t public.$t"; done
    pg "$CLIENT_IMAGE" sh -c "pg_dump --data-only --inserts --rows-per-insert=100 --enable-row-security \
      --no-owner --no-privileges $table_args \"\$PGURL\"" > "$file.tmp"
    grep -q "INSERT INTO public.legal_chunks" "$file.tmp" || die "dump has no legal_chunks rows; not saved"
    mv "$file.tmp" "$file"
    log "Saved $file ($(du -h "$file" | cut -f1)); sha256 $(sha256sum "$file" | cut -c1-16)…"
    ;;
  restore)
    file="${2:-}"; [[ -s "$file" ]] || die "usage: $0 restore FILE.sql"
    log "Before: $(counts)"
    { echo '\set ON_ERROR_STOP on'
      echo 'BEGIN;'
      echo 'SET LOCAL statement_timeout = 0;'
      echo 'TRUNCATE public.legal_chunks, public.legal_sections, public.legal_source_versions, public.legal_sources;'
      cat "$file"
      echo 'COMMIT;'
    } | pg "$CLIENT_IMAGE" sh -c 'psql -X -q -v ON_ERROR_STOP=1 "$PGURL"' >/dev/null \
      || die "restore failed; the transaction was rolled back and nothing changed"
    q "VACUUM (ANALYZE) public.legal_chunks, public.legal_sections, public.legal_source_versions, public.legal_sources" >/dev/null
    log "After:  $(counts)"
    log "RLS forced on $(q "SELECT count(*) FILTER (WHERE relforcerowsecurity) || '/' || count(*) FROM pg_class
      WHERE relnamespace = 'public'::regnamespace AND relkind = 'r' AND relrowsecurity") RLS tables"
    ;;
  *) die "usage: $0 backup | restore FILE.sql" ;;
esac
