# Neon setup for the Render demo

Neon (free plan) hosts the demo database. You run the schema migrations and the demo
data restore **from your own computer**, once. Render's free plan has no shell.

You need: the repo on branch `deploy/render`, `uv`, Docker, and the local Compose
database (`make infra-up`) with the legal knowledge base loaded and embedded.

> Demo data only: the demo lawyer, one `SAMPLE_DATA_NOT_REAL_LAW` case and public
> statute text. Never put client data in this database (DOCS/providers.md).

## 1. Create the project

1. Sign up at <https://neon.com> (GitHub login is fine, no card).
2. **New project**: name `pokkhoai`, Postgres **17**, region **AWS Asia Pacific (Singapore)**
   (same region as the Render service in `render.yaml`).
3. On the project dashboard click **Connect**. Keep database `neondb` and role
   `neondb_owner`. **Turn "Connection pooling" OFF** so the host has no `-pooler`
   in it (asyncpg needs the direct host). Copy the connection string. It looks like:

   ```
   postgresql://neondb_owner:<owner-password>@ep-xxxx-xxxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
   ```

   Below, `<HOST>` means the `ep-....neon.tech` part and `<OWNER_PW>` the password.

## 2. Enable extensions

In Neon open **SQL Editor** (database `neondb`) and run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS citext;
SELECT extname, extversion FROM pg_extension ORDER BY 1;  -- vector must be >= 0.8
```

## 3. Run the bootstrap migrations as the owner role

```bash
cd backend
uv sync
ALEMBIC_BOOTSTRAP_DATABASE_URL='postgresql+asyncpg://neondb_owner:<OWNER_PW>@<HOST>/neondb?sslmode=require' \
  uv run alembic -x bootstrap=true upgrade head
```

`sslmode=require` works with asyncpg: `app/database.py:asyncpg_url` turns it into
asyncpg's `ssl=require` and drops `channel_binding` (asyncpg has no such option).
The last line printed should mention `0019_owner_policy_no_bypass`.

## 4. Set the role passwords

Make three random passwords (URL-safe, so they need no escaping in URLs):

```bash
for r in app_user app_admin_ingest app_owner; do echo "$r: $(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"; done
```

Save them in your password manager, then in the Neon **SQL Editor**:

```sql
ALTER ROLE app_user         PASSWORD '<APP_USER_PW>';
ALTER ROLE app_admin_ingest PASSWORD '<INGEST_PW>';
ALTER ROLE app_owner        PASSWORD '<APP_OWNER_PW>';
```

## 5. Check isolation

```sql
SELECT rolname, rolsuper, rolbypassrls, rolinherit FROM pg_roles WHERE rolname LIKE 'app_%' ORDER BY 1;
-- app_user and app_admin_ingest: rolsuper f, rolbypassrls f. Always.
-- app_owner: rolbypassrls t, OR f plus the owner policies counted below.
SELECT count(*) AS owner_policies FROM pg_policies WHERE policyname = 'app_owner_unrestricted';
SELECT count(*) FILTER (WHERE relforcerowsecurity) AS forced, count(*) AS rls_tables
FROM pg_class WHERE relnamespace = 'public'::regnamespace AND relkind = 'r' AND relrowsecurity;
-- forced = rls_tables (37)
```

## 6. Load the demo data

```bash
cd ..   # repo root
DEMO_LAWYER_PASSWORD='<choose 12+ chars>' deploy/make_demo_dump.sh
NEON_APP_OWNER_URL='postgresql://app_owner:<APP_OWNER_PW>@<HOST>/neondb?sslmode=require' \
  deploy/restore_demo_dump.sh
```

Expect: `Loaded: 2652 legal chunks, 29 approved Acts, 1 user, 1 case` and
`RLS forced on 37/37 RLS tables` (numbers depend on your local knowledge base).
The demo lawyer logs in with `demo.lawyer@example.com` (or `DEMO_LAWYER_EMAIL`) and
the password you chose. `deploy/demo_data.dump` holds that password's hash: it is
git-ignored; delete it when you are done.

## 7. The URL for Render

```
DATABASE_URL=postgresql+asyncpg://app_user:<APP_USER_PW>@<HOST>/neondb?sslmode=require
```

Note the `+asyncpg` and the user `app_user`: the API refuses to start as any other
role, or as a role that bypasses RLS.

## Later migrations

New migrations run as `app_owner` (never the bootstrap URL again):

```bash
cd backend
ALEMBIC_DATABASE_URL='postgresql+asyncpg://app_owner:<APP_OWNER_PW>@<HOST>/neondb?sslmode=require' \
  uv run alembic upgrade head
```

A migration that adds a table with row level security must end with
`SELECT app.ensure_owner_policies()` (as `app_owner`), so the table also works where
`app_owner` has no BYPASSRLS. It does nothing where `app_owner` has BYPASSRLS.

## What changed in the bootstrap for Neon, and why it is safe

Neon's owner role is not a superuser. It has CREATEROLE, but Postgres 16+ lets such
a role mention SUPERUSER, REPLICATION or BYPASSRLS in `ALTER ROLE` only if it holds
that attribute itself. Neon gives BYPASSRLS to `neon_superuser` only in newer
projects, so `CREATE/ALTER ROLE ... BYPASSRLS` may be refused. Tested on a local
Postgres 17 set up like Neon (owner with CREATEROLE/CREATEDB, member of a
`neon_superuser` role, no superuser, both with and without BYPASSRLS):

| Change | Where | Effect on a superuser bootstrap (local Compose) |
|---|---|---|
| Role attributes are set one at a time, only where they differ. app_user / app_admin_ingest must end NOSUPERUSER, NOREPLICATION, NOBYPASSRLS or the migration **fails** | `0001_phase1_baseline.py` | None: same final attributes (checked on a fresh cluster) |
| If BYPASSRLS cannot be granted, app_owner stays NOBYPASSRLS (warning) | `0001` | None (superuser grants it) |
| A non-superuser bootstrap role gets SET (not INHERIT) on app_owner, so `SET ROLE app_owner` works. It already administers app_owner through CREATEROLE | `0001` | None (superusers skip it) |
| `GRANT USAGE ON SCHEMA app ...` run as the schema owner (inside `SET ROLE app_owner`) | `0001`, `0011` | None (same grant, same grantor) |
| A non-superuser bootstrap role may write `alembic_version` (that table only) | `0001` | None |
| New migration: where app_owner lacks BYPASSRLS, each RLS table gets `app_owner_unrestricted`: PERMISSIVE, `FOR ALL TO app_owner USING (true)` | `0019_owner_policy_without_bypassrls.py` | None (no-op when app_owner has BYPASSRLS) |

Why 0019 is needed and does not weaken isolation: the RLS policies call
SECURITY DEFINER helpers owned by `app_owner` (for example the membership checks).
They read RLS tables, and FORCE RLS applies to the owner too, so without BYPASSRLS
they would see nothing and every request would fail (verified: 46 test failures).
The owner policy gives `app_owner`, and only `app_owner`, exactly what BYPASSRLS
gave it. `app_user` and `app_admin_ingest` are not members of `app_owner`, their
policies are unchanged, RLS stays ENABLED and FORCED on all 37 tables, and the API
still refuses to start unless it connects as `app_user` without BYPASSRLS. The full
backend test suite passes as `app_user` against the Neon-like database.

The demo dump uses INSERT rows (not COPY), because Postgres refuses COPY into
tables where RLS applies to the writer.
