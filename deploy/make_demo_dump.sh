#!/usr/bin/env bash
# Build deploy/demo_data.dump: the data the Render demo needs, and nothing else.
#
#   DEMO_LAWYER_PASSWORD='<12+ chars>' deploy/make_demo_dump.sh
#   # optional: DEMO_LAWYER_EMAIL=... DEMO_LAWYER_NAME=... SOURCE_DB=legal_copilot
#
# Needs the local Compose database running (make infra-up) and backend/.env with
# DATABASE_URL for app_user (its password is reused for the scratch database).
#
# How: a throwaway database (pokkho_demo_build) on the local Compose server gets the
# bootstrap migrations, then
#   1. the demo lawyer + one synthetic SAMPLE_DATA_NOT_REAL_LAW case, created through
#      the app's own code (Argon2id hash, organization, stages, audit events);
#   2. the public legal knowledge base copied from SOURCE_DB (legal_sources,
#      legal_source_versions, legal_sections, legal_chunks incl. their embeddings, which
#      must all come from one model: the one Render's EMBEDDING_PROVIDER uses);
#   3. reviewed_by on approved versions re-pointed to the demo lawyer, because the
#      original reviewer accounts are not exported.
# The dump is DATA ONLY of that scratch database (minus alembic_version), so no dev
# accounts, sessions, client documents or real cases can leave this machine. It
# holds the demo lawyer's password HASH: it is git-ignored; do not publish it.
# Rows are INSERTs, not COPY: COPY is refused where RLS applies to the writer (Neon,
# migration 0019). Restore it into Neon with deploy/restore_demo_dump.sh.
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"
BACKEND="$REPO_ROOT/backend"
COMPOSE_FILE="${COMPOSE_FILE:-$REPO_ROOT/compose.yaml}"
DB_SERVICE="${DB_SERVICE:-db}"
SOURCE_DB="${SOURCE_DB:-legal_copilot}"
SCRATCH_DB="pokkho_demo_build"
OUT="$HERE/demo_data.dump"
LEGAL_TABLES=(legal_sources legal_source_versions legal_sections legal_chunks)

: "${DEMO_LAWYER_PASSWORD:?Set DEMO_LAWYER_PASSWORD (12+ characters) for the demo lawyer}"
export DEMO_LAWYER_EMAIL="${DEMO_LAWYER_EMAIL:-demo.lawyer@example.com}"
export DEMO_LAWYER_PASSWORD

log() { printf '[demo-dump] %s\n' "$*"; }
die() { printf '[demo-dump] ERROR: %s\n' "$*" >&2; exit 1; }
dc() { docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" "$@"; }
# Run SQL from stdin as the Compose superuser against database $1.
sql() { dc sh -c 'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1" -tAq' _ "$1"; }
q() { echo "$2" | sql "$1"; }

dc pg_isready -q >/dev/null 2>&1 || die "local database is not running; start it with: make infra-up"

PG_USER="$(dc printenv POSTGRES_USER)"
PG_PORT="${POSTGRES_PORT:-5433}"
urlenc() { python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1"; }
SU_PW="$(urlenc "$(dc printenv POSTGRES_PASSWORD)")"
APP_USER_PW="$(cd "$BACKEND" && uv run --no-sync python -c '
import os, urllib.parse
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
url = make_url(os.environ.get("DATABASE_URL") or dotenv_values(".env").get("DATABASE_URL") or "")
assert url.username == "app_user" and url.password, "backend/.env DATABASE_URL must be app_user with a password"
print(urllib.parse.quote(url.password, safe=""))')"
BASE="127.0.0.1:$PG_PORT/$SCRATCH_DB"

cleanup() { q postgres "DROP DATABASE IF EXISTS $SCRATCH_DB WITH (FORCE)" >/dev/null 2>&1 || true; }
trap cleanup EXIT

[[ "$(q "$SOURCE_DB" "SELECT count(*) FROM public.legal_chunks WHERE embedding IS NULL AND is_active")" == 0 ]] \
  || die "$SOURCE_DB has active chunks without embeddings; run the embed worker first"
EMBEDDING_LABEL="$(q "$SOURCE_DB" "SELECT string_agg(DISTINCT embedding_model || ' v' || embedding_version, ', ')
  FROM public.legal_chunks WHERE is_active")"
[[ "$EMBEDDING_LABEL" != *,* ]] || die "$SOURCE_DB mixes embedding models ($EMBEDDING_LABEL); finish the re-embed first"

log "Creating scratch database $SCRATCH_DB"
q postgres "DROP DATABASE IF EXISTS $SCRATCH_DB WITH (FORCE)"
q postgres "CREATE DATABASE $SCRATCH_DB"

log "Applying migrations"
if ! migrate_log="$(cd "$BACKEND" && ALEMBIC_BOOTSTRAP_DATABASE_URL="postgresql+asyncpg://$PG_USER:$SU_PW@$BASE" \
    uv run --no-sync alembic -x bootstrap=true upgrade head 2>&1)"; then
  echo "$migrate_log" | tail -n 20 >&2
  die "migrations failed"
fi

log "Seeding demo lawyer $DEMO_LAWYER_EMAIL and the synthetic case"
seed_out="$(cd "$BACKEND" && DATABASE_URL="postgresql+asyncpg://app_user:$APP_USER_PW@$BASE" \
  uv run --no-sync python "$HERE/seed_demo.py")"
echo "$seed_out" | grep -v '^DEMO_LAWYER_ID=' || true
DEMO_ID="$(echo "$seed_out" | sed -n 's/^DEMO_LAWYER_ID=//p')"
[[ "$DEMO_ID" =~ ^[0-9a-f-]{36}$ ]] || die "seed did not report the demo lawyer id"

log "Copying the legal knowledge base from $SOURCE_DB"
table_args=""
for t in "${LEGAL_TABLES[@]}"; do table_args+=" -t public.$t"; done
# FKs are checked below instead (reviewed_by points at users not exported).
dc sh -c "{ echo 'SET session_replication_role = replica;';
            pg_dump -U \"\$POSTGRES_USER\" -d '$SOURCE_DB' --data-only --no-owner --no-privileges $table_args; } \
          | psql -X -v ON_ERROR_STOP=1 -U \"\$POSTGRES_USER\" -d '$SCRATCH_DB' -q" >/dev/null

sql "$SCRATCH_DB" <<SQL
UPDATE public.legal_source_versions SET reviewed_by = '$DEMO_ID' WHERE reviewed_by IS NOT NULL;
SQL

log "Checking the scratch database"
check() { [[ "$(q "$SCRATCH_DB" "$2")" == "$3" ]] || die "check failed: $1"; }
check "exactly one user (the demo lawyer)" "SELECT count(*) FROM public.users" 1
check "the user is the demo lawyer" "SELECT email || '/' || role FROM public.users" "${DEMO_LAWYER_EMAIL,,}/lawyer"
check "exactly one case, synthetic" \
  "SELECT count(*) FILTER (WHERE title LIKE 'SAMPLE_DATA_NOT_REAL_LAW%') || '/' || count(*) FROM public.cases" "1/1"
check "no sessions, documents or clients" \
  "SELECT (SELECT count(*) FROM public.sessions) + (SELECT count(*) FROM public.documents) + (SELECT count(*) FROM public.client_profiles)" 0
check "every reviewer exists" \
  "SELECT count(*) FROM public.legal_source_versions v WHERE reviewed_by IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.users u WHERE u.id = v.reviewed_by)" 0
check "every chunk has an embedding" "SELECT count(*) FROM public.legal_chunks WHERE embedding IS NULL AND is_active" 0
chunks="$(q "$SCRATCH_DB" "SELECT count(*) FROM public.legal_chunks")"
approved="$(q "$SCRATCH_DB" "SELECT count(*) FROM public.legal_source_versions WHERE review_status = 'approved'")"
[[ "$chunks" -gt 0 ]] || die "no legal chunks copied"

log "Writing $OUT"
# Only tables that hold rows (empty ones need nothing restored).
dump_args="$(q "$SCRATCH_DB" "SELECT string_agg('-t public.' || table_name, ' ' ORDER BY table_name)
  FROM information_schema.tables
  WHERE table_schema = 'public' AND table_type = 'BASE TABLE' AND table_name <> 'alembic_version'
    AND (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM public.%I', table_name),
                                             false, true, '')))[1]::text::int > 0")"
dc sh -c "pg_dump -U \"\$POSTGRES_USER\" -d '$SCRATCH_DB' --format=custom --compress=9 --data-only \
          --no-owner --no-privileges --rows-per-insert=100 $dump_args" > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
chmod 600 "$OUT"
tables="$(dc pg_restore --list < "$OUT" | awk '/TABLE DATA/ {print $(NF-1)}' | sort | tr '\n' ' ')"
log "Done: $(( $(stat -c %s "$OUT") / 1024 / 1024 )) MB, $approved approved Acts, $chunks chunks, 1 demo lawyer, 1 synthetic case"
log "Embeddings: $EMBEDDING_LABEL (Render's EMBEDDING_PROVIDER must embed queries with this model)"
log "Tables: $tables"
