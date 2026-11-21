#!/usr/bin/env bash
# Restore deploy/demo_data.dump (from make_demo_dump.sh) into Neon.
#
#   export NEON_APP_OWNER_URL='postgresql://app_owner:<pw>@<host>/neondb?sslmode=require'
#   deploy/restore_demo_dump.sh
#
# Connects as app_owner (the table owner) with the DIRECT (non-pooler) host. Runs
# pg_restore from a postgres:17 Docker image, so no local Postgres client is needed.
# The URL is passed to the container as an environment variable, never as an
# argument (it holds a password). One transaction: all rows or none.
# Row level security stays enabled and forced; app_owner writes through its
# BYPASSRLS attribute or the owner-only policy from migration 0019.
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DUMP="${DUMP:-$HERE/demo_data.dump}"
CLIENT_IMAGE="${CLIENT_IMAGE:-postgres:17}"

die() { printf '[restore] ERROR: %s\n' "$*" >&2; exit 1; }
log() { printf '[restore] %s\n' "$*"; }

: "${NEON_APP_OWNER_URL:?Set NEON_APP_OWNER_URL=postgresql://app_owner:...@<direct host>/neondb?sslmode=require}"
[[ -s "$DUMP" ]] || die "$DUMP not found; run deploy/make_demo_dump.sh first"
[[ "$NEON_APP_OWNER_URL" == postgresql://app_owner:* ]] || die "connect as app_owner (postgresql://app_owner:...)"
[[ "$NEON_APP_OWNER_URL" != *-pooler.* ]] || die "use the direct host, not the -pooler host"

pg() { docker run --rm -i --network host -e PGURL="$NEON_APP_OWNER_URL" "$CLIENT_IMAGE" sh -c "$1"; }
psql_q() { pg "psql -X -v ON_ERROR_STOP=1 -tAq \"\$PGURL\" -c \"$1\""; }

[[ "$(psql_q "SELECT current_user")" == app_owner ]] || die "not connected as app_owner"
[[ "$(psql_q "SELECT count(*) FROM public.alembic_version WHERE version_num = '0019_owner_policy_no_bypass'")" == 1 ]] \
  || die "run the alembic bootstrap first (deploy/neon_setup.md step 3)"
existing="$(psql_q "SELECT (SELECT count(*) FROM public.users) + (SELECT count(*) FROM public.legal_chunks)")"
[[ "$existing" == 0 ]] || die "database already has users or legal chunks; restore only into a fresh database"

log "Restoring $(basename "$DUMP") ($(( $(stat -c %s "$DUMP") / 1024 / 1024 )) MB) in one transaction"
pg 'pg_restore --data-only --single-transaction --exit-on-error --no-owner --no-privileges \
      --enable-row-security -d "$PGURL"' < "$DUMP"
psql_q "ANALYZE public.legal_sources, public.legal_source_versions, public.legal_sections, public.legal_chunks"
log "Loaded: $(psql_q "SELECT (SELECT count(*) FROM public.legal_chunks) || ' legal chunks, ' ||
  (SELECT count(*) FROM public.legal_source_versions WHERE review_status = 'approved') || ' approved Acts, ' ||
  (SELECT count(*) FROM public.users) || ' user, ' || (SELECT count(*) FROM public.cases) || ' case'")"
log "RLS forced on $(psql_q "SELECT count(*) FILTER (WHERE relforcerowsecurity) || '/' || count(*) FROM pg_class
  WHERE relnamespace = 'public'::regnamespace AND relkind = 'r' AND relrowsecurity") RLS tables"
