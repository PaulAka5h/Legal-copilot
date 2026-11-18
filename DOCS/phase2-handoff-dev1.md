# Phase 2 Handoff: Backend Dev 1

Status: Draft handoff; Phase 2 exit gate has not passed. This is the honest
handoff state after B9 through B14 implementation work.

## 1. Done and stubbed

- B9: `/health/ready`, password reset, TOTP MFA, recovery codes, case-member
  endpoints, and case audit endpoints.
- B10: central append-only audit writer and append-only database protection.
- B11: organization-scoped lawyer overview, activity, and team APIs.
- B12: hashed single-use invitations, reissue/revoke behavior, and real client
  sessions.
- B13: client visibility tables and RLS, publish/withdraw lifecycle, hearing read,
  tasks, shared documents, notifications, and a `NOT_CONFIGURED` download stub.
- B14: close/reopen APIs and lawyer closed-case write denial.

Test count: 42 passing against local Compose PostgreSQL as `app_user`.

Not verified by the required exit-gate module:
- one full two-lawyer/two-client/two-case scenario across every lawyer and client endpoint.
- client closed-case and reopen behavior in a single real-client session scenario.
- cross-tenant client visibility and withdrawn/draft isolation across the complete portal.

Stubbed:
- email sender and invitation/reset delivery.
- object download URL.
- no Dev 2 event bus/SSE or job APIs.
- shared document foreign key, pending Dev 2's documents table.

## 2. Migrations

All revisions below are local drafts and unreviewed by Akash and Backend Dev 2:

- `0001_phase1_baseline`
- `0002_auth_support`
- `0003_session_revocation`
- `0004_b9_auth_support`
- `0005_b10_audit_writer`
- `0006_b12_invitations`
- `0007_b13_client_visibility`

No migration is approved for a shared database.

## 3. Contracts Dev 2 can rely on

- Sessions use `lc_session`, argon2id credentials, and transaction-local
  `app.current_user_id()`.
- `app_user` is the only application database role; it has no superuser or
  BYPASSRLS capability.
- `CaseAccess` loads active case membership and returns permission flags.
- Audit inserts use `app.write_audit_event(...)` in the same transaction as the
  change. Direct `app_user` audit INSERT is revoked.
- Workers acting for a user must set `app.current_user_id` transaction-locally
  and must not use a superuser/table-owner connection.
- API failures use RFC 7807 `application/problem+json`.

## 4. Dev 2 dependencies

- Documents and pages table schema, including the expected document UUID lifecycle.
- Download URL call/signature and storage configuration.
- Job payload contract if jobs affect case data.
- Whether `client_shared_documents.document_id` can now reference the final
  documents table.

## 5. Open questions and defaults

- Client login: TRD hashed single-use invitation flow was used.
- Shared documents: plain UUID column is used until the documents table exists.
- Hearings: table from `database.md` was created; client reads confirmed upcoming
  hearings. Lawyer write APIs wait for Phase 7.
- Summaries: no separate summary table was added; approved hearing summaries are
  treated as a kind of client-visible update.
- Organization selection: leave unchanged; multiple memberships still produce
  409 in organization-dependent flows.
- Jobs/SSE: left to Dev 2.
- Email: `NOT_CONFIGURED` in production/development delivery is stubbed.

## 6. Frontend integration changes

- Replace mock `lc_session` handling with the real cookie contract.
- Switch login/register flows to real `/api/v1/auth/*` endpoints.
- Replace client ID/password mock login with invitation acceptance and password
  setup.
- Use `/api/v1/lawyer/dashboard/*` and `/api/v1/lawyer/team` response models.
- Use `/api/v1/client/*` models; never import lawyer-only types into client pages.
- Replace mock download URLs with the `NOT_CONFIGURED` response until Dev 2 storage
  is wired.
