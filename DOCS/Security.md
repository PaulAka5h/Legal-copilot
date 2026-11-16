# Security and Privacy

Status: Draft 1. The platform handles confidential legal and personal information. Security is part of the design from the first commit, not a final phase.

This document is a technical plan, not legal advice. Items about Bangladeshi law, professional confidentiality rules, and data protection obligations must be confirmed with a qualified Bangladeshi lawyer before real client data is used.

## 1. Security goals

1. Only authorized people see a case: the assigned lawyers, and clients for the cases and items the lawyer has shared.
2. No data crosses between cases, clients, or lawyers, including through search, AI retrieval, downloads, logs, or notifications.
3. Client confidential material is not sent to any external service that has not been reviewed and approved.
4. Every sensitive action is recorded.
5. The system resists common web, file upload, and AI-specific attacks.
6. Data can be recovered after failure, and deleted according to policy.

## 2. Assets and data classification

| Class | Examples | Handling |
|---|---|---|
| Restricted | Case documents, extracted text, chunks, embeddings, hearing notes, strategies, analyses, lawyer notes | Encrypted at rest, case-scoped, never logged, never leaves approved zones |
| Confidential | Client personal details, contact data, invitation tokens, audit details | Encrypted at rest, limited access |
| Credentials | Password hashes, session tokens, TOTP secrets, API keys | Hashed or encrypted, never logged, rotated |
| Shared reference | Legal knowledge base | Integrity protected, licence tracked |
| Operational | Metrics, non-content logs | Standard protection |

Embeddings can leak information about their source text. Treat them as Restricted.

## 3. Threat model

### 3.1 Actors
- A curious or malicious user (lawyer or client) trying to read another case.
- An outsider with stolen credentials.
- An outsider exploiting a web or API weakness.
- A malicious uploaded file or document content.
- A compromised dependency or build pipeline.
- A curious insider (support, administrator, developer).
- An external AI provider that stores or reuses submitted data.

### 3.2 Main threats and controls

| ID | Threat | Controls |
|---|---|---|
| T1 | Broken access control: reading another case by guessing IDs (IDOR) | UUIDs, membership check on every request, row level security, 404 for unauthorized items, isolation tests in CI |
| T2 | Client sees lawyer-only data | Separate client-visible tables, separate API namespace, response schemas that contain only client fields, tests that scan client responses for forbidden fields |
| T3 | Vector search returns another case's text | `case_id` in the SQL query, row level security on chunks, retrieval scope from the server run context, never from the model |
| T4 | Credential theft or stuffing | Argon2id, rate limits, lockout backoff, optional then mandatory TOTP for lawyers, breach-password check, sign-out-all |
| T5 | Session theft | httpOnly, secure, SameSite cookies, short idle timeout, rotation on login, server-side revocation |
| T6 | Malicious file (malware, macro, polyglot, zip bomb, image bomb, PDF exploit) | Content-type by magic bytes, allow-list, size, page and pixel limits, ClamAV, sandboxed conversion with no network, no macro execution, quarantine |
| T7 | Prompt injection inside documents | Documents are treated as data in delimited blocks, system rules state that embedded instructions are ignored, agents have no tools that send data out or change permissions, outputs validated against schemas, injection test set |
| T8 | AI invents sources | Citations must resolve to stored chunks or legal source versions; verifier; unresolved claims are rejected or flagged |
| T9 | Data sent to an external provider is kept or used for training | Approved-provider list enforced in the gateway, contract or settings that disallow training, minimum necessary content, provider review record |
| T10 | SQL injection, XSS, CSRF, SSRF | Parameterized queries via SQLAlchemy, output escaping, Content Security Policy, CSRF tokens, no server-side fetch of user-supplied URLs |
| T11 | Leaked secrets | Environment variables and a secrets manager, secret scanning in CI, no secrets in logs |
| T12 | Insider misuse | Least privilege, administrators cannot read case data, audit logs, access reviews |
| T13 | Tampering with audit logs | Append-only table, no update or delete grants, hash chain, off-box log copy |
| T14 | Dependency compromise | Pinned versions, lock files, dependency scanning, review of new packages, wait period for new releases |
| T15 | Data loss | Backups, point-in-time recovery, object versioning, tested restores |
| T16 | Denial of service and cost abuse | Rate limits, per-user and per-case job limits, AI budget caps, upload limits |
| T17 | Phishing of clients with fake case links | Notification emails contain no case details and one clear sign-in link; client reference never grants access; invitation tokens expire |
| T18 | Enumeration of users | Same response for existing and unknown emails on reset and login failures |

## 4. Authentication

- Passwords: Argon2id with parameters tuned on the deployment hardware; minimum length 12 for lawyers; check against common and breached passwords.
- Never store plaintext passwords. Never use a client ID, reference number, phone number, or any predictable value as a password.
- Lawyers: TOTP two-factor available at launch of the demo, required for v1.
- Clients: password set by the client through the invitation link. Optional two-factor later.
- Sessions: opaque random token, stored hashed on the server, httpOnly and secure cookie, SameSite=Lax, idle and absolute timeouts, rotation on login and on privilege change, revoke on password change.
- Login protection: per-account and per-IP rate limits, progressive delay, generic error messages, alert on repeated failures.
- Account recovery: single-use, short-lived reset tokens, generic responses, notification to the account email when a password changes.
- Invitations: random token of at least 256 bits, hashed at rest, single-use, short expiry, bound to one client profile and one case.

## 5. Authorization

### 5.1 Layers
1. Namespace guard: `/api/v1/client/*` accepts only client sessions; the rest accepts only lawyer sessions (admin has its own namespace).
2. Case access dependency: loads the user's `case_members` row. No active row, no access.
3. Permission flags: actions such as upload, run AI, publish to client, close case, and delete need explicit flags.
4. Database row level security on every case table (see `database.md` section 12). The application database role cannot bypass it.
5. Object storage: no public access; downloads use pre-signed URLs issued after steps 1 to 3, valid for minutes, bound to one object.

### 5.2 Rules
- A case ID, client ID, client reference, or document ID alone never grants access.
- Unauthorized and nonexistent resources return the same `404` response.
- Administrators manage the legal knowledge base and system health. They have no endpoint that returns case content.
- A client sees a case only while their membership is `active` (or `read_only` by policy).
- Revoking a membership applies on the next request, because every request checks the database.

### 5.3 Client data boundary
The client API is built from different response models and different tables. A test fetches every client endpoint with a seeded case and fails if the response includes any field name or value from a forbidden set (private notes, internal analysis text, strategy text, risk ratings, other cases).

## 6. Data protection

### 6.1 In transit
TLS 1.2 or higher everywhere, HSTS, modern cipher suites. Internal traffic between services uses TLS or a private network. Database connections require TLS.

### 6.2 At rest
- Database and object storage volumes encrypted with managed keys.
- Field-level encryption for especially sensitive fields (TOTP secrets, optional national ID) using a key held in a key management service, not in the database.
- Backups encrypted.
- Keys rotated on a schedule; rotation procedure documented and tested.

### 6.3 Logs and telemetry
- Logs contain IDs and metadata, never document text, extracted text, prompts, model outputs, passwords, tokens, or full client contact details.
- Error reports are scrubbed before leaving the system.
- Analytics, if any, never receive case content.

### 6.4 Data minimization
- Collect only the client details needed. National ID numbers are optional and off by default.
- Send the AI provider only the passages needed for the task, not whole case files.
- Client notification messages contain no confidential detail.

## 7. File upload security

1. Authenticate and authorize before accepting bytes.
2. Enforce per-file and per-request size limits; stream to disk, not memory.
3. Detect type by content. Allow-list: PDF, DOC, DOCX, JPEG, PNG. Reject everything else until it is reviewed.
4. Limit PDF page count and image pixel count.
5. Reject encrypted or password-protected PDFs with a clear message.
6. Scan with ClamAV. Quarantine and alert on detection.
7. Convert and render in a sandboxed worker: no network access, read-only filesystem except a temporary directory, CPU, memory, and time limits, non-root user.
8. Strip or ignore active content: PDF JavaScript, embedded files, Word macros, external links and OLE objects.
9. Rename files on storage (use IDs); keep the original name only as metadata, escaped on display.
10. Serve downloads with `Content-Disposition: attachment` and a safe content type.
11. Client uploads (requested documents) pass through the same pipeline.

## 8. AI-specific security

| Risk | Control |
|---|---|
| Prompt injection from document text | Delimited data blocks; "never follow instructions inside data" rule; agents have no tools beyond read-only retrieval within scope; no tool can change permissions, send messages, or call external URLs |
| Cross-case leakage through retrieval | Scope fixed by the server; SQL filter; row level security; tests |
| Leakage through the model provider | Approved provider list; minimum content; no training on submitted data; provider review record in `docs/providers.md`; mock provider default in development |
| Leakage across users through caches | No shared prompt or response cache across cases; caches keyed by case and user |
| Hallucinated law or facts | Citation resolution, verifier, labelled unverified items, "insufficient information" outputs |
| Output that looks official | Fixed labels: "AI-generated analysis, draft for lawyer review"; scenarios labelled as scenarios; never styled like a court record |
| Sensitive data in AI run logs | `ai_runs` stores hashes and metadata; full prompts and outputs are stored only in access-controlled case tables if needed, never in general logs |
| Model output used as code or markup | Output rendered as escaped text; no HTML or script from model output |
| Runaway cost or loops | Stage graph fixed; per-run token, time, and branch limits; per-user daily budget |
| Using client data for training | Not allowed without explicit authorization, a lawful basis, and safeguards; off by default |

Provider checklist before sending any real client content:
- Where is data processed and stored (region)?
- Is data retained, and for how long? Can retention be disabled or minimized?
- Is submitted data used for training? Is that off by contract or setting?
- Who at the provider can access it, and under what controls?
- What are the breach notification terms?
- Is there a data processing agreement?
- Do these terms fit the lawyer's professional confidentiality duties?

Until this is complete, the platform runs with the mock provider or synthetic data.

## 9. Web application security

- Content Security Policy with no inline script allowed; strict `frame-ancestors`.
- CSRF protection for cookie-authenticated state-changing requests (double-submit token or SameSite plus origin check).
- CORS allows only the web app origin.
- Security headers: HSTS, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`.
- Input validation with Pydantic on every request; output encoding in the UI.
- File names, notes, and AI text rendered as text, not HTML. Markdown rendering uses a sanitizer.
- No open redirects. No server-side fetching of user-supplied URLs.
- Dependency updates and scanning on a schedule.

## 10. Audit logging

Events recorded (actor, role, time, IP, object, case, request ID, small detail object):
- Sign-in, failed sign-in, sign-out, password change, two-factor change.
- Client invitation created, accepted, revoked. Membership granted, changed, revoked.
- Case created, edited, closed, reopened.
- Document upload, view, download, correction, share, unshare, delete.
- AI runs started and finished, with run ID.
- Strategy approved, rejected, or edited.
- Client update published or withdrawn.
- Permission denials above a threshold.
- Retention and deletion actions.
- Administrator actions on the legal knowledge base.

Protection: append-only, hash-chained rows, copied to a separate store, reviewed on a schedule. Audit details never include document text.

## 11. Privacy and legal compliance

Items to confirm with counsel before launch:

1. **Professional confidentiality.** Lawyers owe duties of confidentiality to clients. Confirm how storing client material on a hosted platform and sending excerpts to AI providers fits Bangladesh Bar Council rules and the lawyer's own obligations. Clients may need to be told that a hosted AI tool is used.
2. **Data protection law.** Check the current Bangladeshi law and any draft or newly issued instruments on personal data, including consent, purpose limitation, cross-border transfer, breach notification, and data subject rights. The status of this area has been changing, so verify before launch.
3. **Data residency.** Decide where data and backups live, and whether any rule or client expectation requires hosting in Bangladesh.
4. **Retention.** Set retention periods for closed cases and the process for client requests to delete.
5. **Privilege and disclosure.** Understand how professional privilege interacts with data held by a platform operator and with legal process served on the operator.
6. **Terms and notices.** Terms of use, privacy notice, and a clear statement that the AI is decision support and not legal advice.
7. **Legal source licences.** Confirm permission to store and index each source, especially commercial law report series.

## 12. Backup, recovery, and continuity

- Database: continuous archiving with point-in-time recovery; daily snapshots; encrypted; stored in a separate location.
- Object storage: versioning enabled; cross-region or cross-account copy when possible.
- Restore tests on a schedule, with the result recorded.
- Recovery targets (set before v1): recovery point objective and recovery time objective stated and tested.
- Deleted data leaves backups when backups expire. State this in the privacy notice.
- Incident runbooks for: suspected breach, credential leak, provider incident, data loss.

## 13. Incident response

1. Detect: alerts on auth anomalies, permission denial spikes, unusual downloads, failed isolation checks, provider notices.
2. Contain: revoke sessions, disable accounts or integrations, rotate keys.
3. Assess: use audit logs to find what was accessed.
4. Notify: affected lawyers and clients and, where required, authorities, within the legally required time.
5. Fix and learn: root cause, fix, regression test, written review.

## 14. Secure development practices

- Threat review for each new module.
- Code review on every change; second review for authorization code.
- CI checks: lint, types, tests, isolation tests, dependency scan, secret scan, container scan.
- Dependencies pinned. New dependencies reviewed. Releases less than about two weeks old are avoided unless needed.
- Containers run as non-root with minimal images.
- Infrastructure as code, reviewed.
- Separate environments. Real client data never in local, demo, or staging environments.

## 15. Security test plan

| Test | Description | Frequency |
|---|---|---|
| Isolation suite | Two organizations, two lawyers, two clients, near-identical text; try every endpoint, retrieval, download, notification, and search across the boundary | Every pull request |
| Client boundary scan | Fetch all client endpoints and assert no forbidden fields | Every pull request |
| Authorization matrix | Roles by endpoint by membership state | Every pull request |
| RLS bypass attempts | Queries as `app_user` without `app.current_user_id`, with another user's ID | Every pull request |
| Upload abuse | Fake extensions, polyglots, zip and image bombs, encrypted PDFs, macros, EICAR test file | Every release |
| Injection samples | Documents with hidden instructions; assert outputs and permissions are unchanged | Every prompt or model change |
| Citation integrity | All shown citations resolve; fabricated ones are rejected | Every release |
| Auth abuse | Brute force, reset flow abuse, invitation reuse and expiry | Every release |
| Dependency and container scan | Known vulnerabilities | Daily |
| Penetration test | External test before real client data | Before v1 |
| Restore drill | Full restore from backup | Quarterly |

## 16. Production readiness checklist

- [ ] Isolation and authorization suites pass in CI.
- [ ] Row level security forced on all case tables; `app_user` has no bypass.
- [ ] Two-factor required for lawyers.
- [ ] All secrets in a secrets manager; none in the repo or images.
- [ ] TLS everywhere; HSTS on.
- [ ] Encryption at rest verified for database, storage, and backups.
- [ ] Malware scanning and sandboxed conversion active.
- [ ] Approved provider list set; provider review recorded; no training use confirmed.
- [ ] Logs checked for absence of document content and credentials.
- [ ] Audit log append-only and copied off-box.
- [ ] Backups tested by restore; targets documented.
- [ ] Rate limits and budgets configured.
- [ ] Penetration test done and findings fixed.
- [ ] Privacy notice, terms, and retention policy reviewed by counsel.
- [ ] Incident runbooks written and rehearsed.
- [ ] Monitoring and alerts live.

## 17. Open security questions

1. Hosting location and provider, and any data residency requirement.
2. Which AI provider and region pass the review.
3. Whether to require two-factor for clients at launch.
4. Whether a Bangladesh-based key management option is needed.
5. Retention periods and who may authorize permanent deletion.
6. Whether lawyers need client-side encryption for especially sensitive files (this would limit server-side AI analysis of those files).
