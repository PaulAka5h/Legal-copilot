#!/usr/bin/env bash
# Back up / restore the legal_chunks vectors of the LOCAL Compose database, so a
# switch of embedding model (python -m app.rag.embed reembed) can be rolled back.
#
#   deploy/embeddings_backup.sh backup  [TAG]   # default TAG: e5_<yyyymmdd>
#   deploy/embeddings_backup.sh restore TAG
#   deploy/embeddings_backup.sh list
#
# backup copies (id, content_hash, embedding, embedding_model, embedding_version,
# embedded_at) of every chunk into embedding_backup.legal_chunks_<TAG> in the same
# database, and also writes backups/embeddings_<TAG>.dump (pg_dump custom format,
# git-ignored) so the copy survives a dropped database:
#   docker compose exec -T db psql -U postgres -d legal_copilot -c 'CREATE SCHEMA IF NOT EXISTS embedding_backup'
#   docker compose exec -T db pg_restore -U postgres -d legal_copilot < backups/embeddings_<TAG>.dump
# restore writes those vectors and labels back onto chunks whose id AND content_hash
# still match (changed chunks are counted, not touched), in one transaction.
# Runs as the Compose superuser. Public statute text vectors only, no case data.
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$REPO_ROOT/compose.yaml}"
DB_SERVICE="${DB_SERVICE:-db}"
DB="${SOURCE_DB:-legal_copilot}"
OUT_DIR="$REPO_ROOT/backups"

die() { printf '[embeddings-backup] ERROR: %s\n' "$*" >&2; exit 1; }
log() { printf '[embeddings-backup] %s\n' "$*"; }
dc() { docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" "$@"; }
q() { echo "$1" | dc sh -c 'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1" -tAq' _ "$DB"; }

dc pg_isready -q >/dev/null 2>&1 || die "local database is not running; start it with: make infra-up"

cmd="${1:-}"
tag="${2:-}"
if [[ "$cmd" == backup && -z "$tag" ]]; then tag="e5_$(date +%Y%m%d)"; fi
if [[ "$cmd" != list ]]; then
  [[ "$tag" =~ ^[a-z0-9_]{1,40}$ ]] || die "TAG must be 1-40 chars of a-z, 0-9, _"
fi
table="embedding_backup.legal_chunks_$tag"

case "$cmd" in
  backup)
    [[ "$(q "SELECT to_regclass('$table') IS NULL")" == t ]] || die "$table already exists; pick another TAG"
    q "CREATE SCHEMA IF NOT EXISTS embedding_backup;
       REVOKE ALL ON SCHEMA embedding_backup FROM PUBLIC;
       CREATE TABLE $table AS
         SELECT id, content_hash, embedding, embedding_model, embedding_version, embedded_at
         FROM public.legal_chunks;
       ALTER TABLE $table ADD PRIMARY KEY (id);"
    log "Copied: $(q "SELECT count(*) || ' chunks (' || count(embedding) || ' with vectors), models: ' ||
      string_agg(DISTINCT embedding_model || ' v' || embedding_version, ', ') FROM $table")"
    mkdir -p "$OUT_DIR"
    dc sh -c "pg_dump -U \"\$POSTGRES_USER\" -d '$DB' --format=custom --no-owner --no-privileges \
              -n embedding_backup -t '$table'" > "$OUT_DIR/embeddings_$tag.dump.tmp"
    mv "$OUT_DIR/embeddings_$tag.dump.tmp" "$OUT_DIR/embeddings_$tag.dump"
    log "Wrote backups/embeddings_$tag.dump ($(( $(stat -c %s "$OUT_DIR/embeddings_$tag.dump") / 1024 / 1024 )) MB)"
    ;;
  restore)
    [[ "$(q "SELECT to_regclass('$table') IS NOT NULL")" == t ]] || die "$table not found (restore the .dump first)"
    q "BEGIN;
       UPDATE public.legal_chunks c
       SET embedding = b.embedding, embedding_model = b.embedding_model,
           embedding_version = b.embedding_version, embedded_at = b.embedded_at
       FROM $table b
       WHERE b.id = c.id AND b.content_hash = c.content_hash;
       COMMIT;"
    log "Restored from $table. Now: $(q "SELECT string_agg(m, ', ') FROM (SELECT embedding_model || ' v' ||
      embedding_version || ': ' || count(*) || ' chunks, ' || count(embedding) || ' with vectors' AS m
      FROM public.legal_chunks GROUP BY embedding_model, embedding_version) s")"
    log "Chunks changed since the backup (not restored): $(q "SELECT count(*) FROM public.legal_chunks c
      LEFT JOIN $table b ON b.id = c.id WHERE b.id IS NULL OR b.content_hash <> c.content_hash")"
    log "Set EMBEDDING_PROVIDER back to local (or hf_api) for these vectors."
    ;;
  list)
    q "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
       WHERE n.nspname = 'embedding_backup' AND c.relkind = 'r' ORDER BY 1"
    ;;
  *) die "usage: $0 backup [TAG] | restore TAG | list" ;;
esac
