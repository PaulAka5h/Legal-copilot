# Deploy the demo for free: Render + Neon + Backblaze B2 + Gemini

Branch: `deploy/render`. Cost: 0. Nothing here needs a credit card.

```
Browser ──► Vercel (Next.js frontend, proxies /api/v1) ──► Render free web service (FastAPI, Docker, 512 MB)
                                                             ├─► Neon Postgres (pgvector, RLS)
                                                             ├─► Backblaze B2 (uploaded documents)
                                                             └─► Gemini API (analysis + search query rewriting; mock fallback)
   (search embeddings: multilingual-e5-small ONNX int8 inside the Render container)
```

> **SYNTHETIC DEMO DATA ONLY.** Search text and case facts are sent to Gemini; the database, files and server are third-party free tiers that have not
> passed the review in `DOCS/providers.md`. Use only `SAMPLE_DATA_NOT_REAL_LAW` cases.
> `APP_ENV` stays `development` on purpose: the code refuses the Gemini LLM in
> `production`.

> **Knowledge base: after the cutover in section 8, the full bdlaws corpus (1,176 Acts,
> 39,587 chunks) embedded with multilingual-e5-small inside the container, all approved
> under the note "Bulk bdlaws import; spot-checked 5 Acts (138, 952, 180, 1054, 1124)
> against source; not individually reviewed by a lawyer".** Before it (history below):
> **19 Acts (717 chunks), embedded with Gemini.** The free
> Gemini tier allows 1,000 embedding requests per day, so the demo carries only Acts
> whose every chunk has a Gemini vector (no Act is half-embedded, no model is mixed).
> The full corpus pipeline exists and runs on e5: 29 Acts (2,652 chunks) are ingested
> and embedded locally, and a dry run of the whole bdlaws dataset plans 1,176 Acts,
> 39,637 chunks (`DOCS/status.md`). Acts in the demo: Negotiable Instruments Act 1881,
> Police Act 1861, Divorce Act 1869, Specific Relief Act 1877, Limitation Act 1908,
> নারী ও শিশু নির্যাতন দমন আইন ২০০০, অর্থ ঋণ আদালত আইন ২০০৩, and 12 smaller Acts
> (`deploy/demo_acts.txt`).

What to expect from free plans: the Render service **sleeps after 15 minutes**
without traffic and takes about a minute to wake; Neon also pauses and wakes on the
first query; the Gemini free tier allows 100 embedding requests per minute and 1,000
per day per Google project, shared by everything that uses the key. Each search uses
one call, each analysis about two per confirmed fact. When the quota runs out, search
and analysis fall back to labelled keyword-only retrieval until it resets (midnight
Pacific time).

Keep a scratch note open. You will collect these values:

| Value | From step |
|---|---|
| `DATABASE_URL` (app_user) | 1 |
| `MINIO_ENDPOINT`, `MINIO_REGION`, `MINIO_BUCKET`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` | 2 |
| `GEMINI_API_KEY` | 3 |
| Render URL (`https://....onrender.com`) | 5 |
| Vercel URL (`https://....vercel.app`) | 6 |
| Demo lawyer email + password | 1 |

---

## 1. Neon (database)

Follow **`deploy/neon_setup.md`** steps 1 to 7. In short: create a Postgres 17 project
in AWS Singapore, enable `vector`, `pg_trgm`, `citext`, run the alembic bootstrap
with the owner role, set the three role passwords, build and restore the demo dump.
At the end you have:

```
DATABASE_URL=postgresql+asyncpg://app_user:<APP_USER_PW>@<ep-....neon.tech>/neondb?sslmode=require
```

and the demo lawyer login (`demo.lawyer@example.com` + the password you chose).

## 2. Backblaze B2 (document storage)

1. Go to <https://www.backblaze.com/sign-up/cloud-storage> and create an account.
2. Left menu **B2 Cloud Storage → Buckets → Create a Bucket**:
   - Bucket name: something unique, e.g. `pokkhoai-demo-<random letters>`
   - Files in Bucket are: **Private**
   - Default Encryption: **Enable**
   - Click **Create a Bucket**.
3. On the new bucket card, copy **Endpoint**, e.g. `s3.us-west-004.backblazeb2.com`.
   - `MINIO_ENDPOINT` = that host exactly. **No `https://`, no `/` or bucket path.**
   - `MINIO_REGION` = the middle part, e.g. `us-west-004`.
   - `MINIO_BUCKET` = the bucket name.
4. Left menu **Application Keys → Add a New Application Key**:
   - Name: `pokkhoai-render`
   - Allow access to Bucket(s): **only your bucket**
   - Type of Access: **Read and Write**
   - Click **Create New Key**. Copy **keyID** → `MINIO_ACCESS_KEY` and
     **applicationKey** → `MINIO_SECRET_KEY` now: the key is shown only once.

The app talks to B2 with the same `minio` client it uses locally (`MINIO_SECURE=true`).

## 3. Gemini API key (analysis + search query rewriting)

<https://aistudio.google.com/apikey> → **Create API key** → copy → `GEMINI_API_KEY`.
Free tier, synthetic data only. The same key serves two things:

- **Query embeddings: not any more after the cutover (section 8):** `EMBEDDING_PROVIDER=e5_small_onnx`
  embeds queries inside the container. `SEARCH_QUERY_REWRITE=true` sends each new search query
  (and each analysed fact) to the LLM once to get Bangla + English variants and keywords; if the
  call fails the plain query is searched (warning `query_rewrite_failed`).
- **Before the cutover: query embeddings (required).** `EMBEDDING_PROVIDER=gemini` embeds every search
  and analysis query with `gemini-embedding-001` (1024 dims, `RETRIEVAL_QUERY`). The
  demo knowledge base in `deploy/demo_data.dump` was embedded with the same model
  (`RETRIEVAL_DOCUMENT`), so the vectors match. Without a key, search answers
  `503 NOT_CONFIGURED`.
- **Analysis (optional).** `LLM_PROVIDER=gemini`: `GEMINI_MODEL=gemini-3.5-flash-lite`.
  On 429/503 it is retried 3 times (2 s, 5 s, 10 s), then `GEMINI_FALLBACK_MODEL=gemini-3.5-flash`
  gets the same treatment, then the labelled mock (`ai_mock`). All LLM calls in one request
  share a 100 s budget, so the API answers inside Vercel's `BACKEND_TIMEOUT_MS=120000`.
  Render logs show `llm.answered` with the model that answered, or `llm.fallback_to_mock`.

No Hugging Face account is needed any more.

## 4. Push the branch

```bash
git push -u origin deploy/render
```

## 5. Render (API)

1. Go to <https://render.com> → **Get Started** → **Sign up with GitHub**.
2. Allow Render to see the `Legal-copilot` repository (all repos or just this one).
3. Top right **New + → Blueprint**.
4. Pick the repository, branch **`deploy/render`**. Render reads `render.yaml` and
   shows one service, `pokkhoai-api` (Docker, Free, Singapore).
5. Blueprint name: `pokkhoai`. Fill in every empty value:

   | Key | Paste |
   |---|---|
   | `APP_ORIGIN` | `https://<your-vercel-project>.vercel.app` (step 6; no trailing `/`. If you do not know it yet, type your intended project name, and fix it after step 6) |
   | `DATABASE_URL` | from step 1 |
   | `MINIO_ENDPOINT` / `MINIO_REGION` / `MINIO_BUCKET` | from step 2 |
   | `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | B2 keyID / applicationKey |
   | `GEMINI_API_KEY` | from step 3 (analysis and search query rewriting) |

   Everything else is preset by `render.yaml`: `APP_ENV=development`,
   `SESSION_COOKIE_SECURE=true`, `EMBEDDING_PROVIDER=e5_small_onnx` (model built into
   the image), `SEARCH_QUERY_REWRITE=true`, `LLM_PROVIDER=gemini`,
   `LLM_APPROVED_PROVIDERS=gemini,mock`, `MALWARE_SCANNER=none`, `MINIO_SECURE=true`,
   `OCR_DPI=250`, and a generated `MFA_ENCRYPTION_KEY`.
6. Click **Apply**. The first build takes about 5 to 10 minutes
   (`backend/Dockerfile.render`: Python 3.12 slim + Tesseract ben/eng, no torch).
7. When the service shows **Live**, copy its URL from the top of the service page,
   e.g. `https://pokkhoai-api.onrender.com`, and open `<URL>/health`. It must show
   `{"status":"ok"}`. `<URL>/health/ready` shows `{"status":"ready"}` once Neon answers.

## 6. Vercel (frontend)

1. <https://vercel.com> → **Sign up with GitHub** → **Add New… → Project** →
   import `Legal-copilot`.
2. **Root Directory**: `frontend`. Framework preset: Next.js.
3. **Environment Variables** (all environments):

   | Key | Value |
   |---|---|
   | `BACKEND_URL` | your Render URL, e.g. `https://pokkhoai-api.onrender.com` |
   | `BACKEND_API_URL` | the same Render URL |
   | `APP_ORIGIN` | your Vercel URL, e.g. `https://pokkhoai.vercel.app` |
   | `MOCK_AUTH` | `false` |
   | `BACKEND_TIMEOUT_MS` | `120000` (covers Render's cold start) |

4. **Deploy**. Then **Settings → Git → Production Branch** = `deploy/render`, and
   redeploy (Deployments → ⋯ → Redeploy) so the production URL serves this branch.
5. If the final Vercel URL differs from what you typed in Render's `APP_ORIGIN`:
   Render → `pokkhoai-api` → **Environment** → edit `APP_ORIGIN` → **Save, rebuild,
   and deploy**. Both sides must hold exactly the same origin, or every form post
   answers `403 Request origin is not allowed`.

The browser only talks to Vercel; Vercel forwards `/api/v1/*` to Render, so the
session cookie stays on the Vercel domain (`Secure`, `HttpOnly`, `SameSite=Lax`).

## 7. Smoke test

From the repo root on your machine:

```bash
cd backend
DEMO_LAWYER_PASSWORD='<demo password>' uv run python ../deploy/smoke_test.py \
  --api https://pokkhoai-api.onrender.com --origin https://pokkhoai.vercel.app
```

Expected (the first request may take a minute while Render wakes up):

```
[PASS] GET /health: HTTP 200
[PASS] GET /health/ready (Neon): HTTP 200
[PASS] login as demo lawyer: HTTP 200
[PASS] synthetic demo case listed: 1 case(s)
[PASS] legal search: HTTP 200, 5 hits in ..., embeddings gemini-embedding-001, top: ...
[PASS] case analysis: HTTP 201 ..., status succeeded, origin ai (gemini) ...
[PASS] OCR upload to B2: HTTP 201, ready ...
ALL PASSED
```

Then in a browser: open the Vercel URL → sign in as the demo lawyer → open the
`SAMPLE_DATA_NOT_REAL_LAW Rahman Traders v. Karim Enterprises` matter → **Facts**:
add and confirm a fact (e.g. the cheque fact from the smoke test) → **Analysis** →
**Run analysis** → findings cite Negotiable Instruments Act sections. (The web app has
no free-text legal search screen; the search API, `POST /api/v1/lawyer/cases/{id}/research/search`,
is exercised by the smoke test.)

If the Gemini embedding quota is used up, search and analysis do not fail: they fall
back to keyword-only (full-text) retrieval, the API returns
`retrieval_mode: "keyword_only"` plus a `keyword_only_fallback` warning, and the
Analysis panel shows a "Keyword-only search" notice. In that mode a provision is used
only if it shares at least 3 content words with the fact (a heuristic, not calibrated).

## 8. Full-corpus cutover (e5-small, 1,176 Acts)

Replaces the 19-Act Gemini-embedded knowledge base in Neon with the full bdlaws corpus
(1,176 Acts, 35,063 sections, 39,587 chunks) embedded with `intfloat/multilingual-e5-small`
(ONNX int8, 384 dims), and switches Render to embed queries with the same model inside
the container. Only the four `legal_*` tables change; users, cases, facts, analyses,
hearings and documents are not touched (the cutover checks every other table's row count).
Saved analyses cite chunk ids: a chunk keeps its id when its text is unchanged (rehearsal:
663 of 717 old chunks kept their ids, all 7 cited chunks still present).

Rehearsed end to end on a Neon-like Postgres 17 (non-superuser owner, RLS forced 37/37,
app_owner without BYPASSRLS) holding the demo dump: see "Measured results" below.

Run in this order. Stop at the first step that fails.

1. **Local export** (once; reads `legal_copilot_full`, refuses unless every chunk has an
   e5-small v1 vector and every version is approved):
   `SOURCE_DB=legal_copilot_full deploy/export_legal_corpus.sh` → `deploy/corpus_e5small/`
   (284 MB, git-ignored, public statute text only).
2. **Back up Neon's current legal tables** (the rollback copy, about 10 MB):
   ```bash
   export NEON_APP_OWNER_URL='postgresql://app_owner:<APP_OWNER_PW>@<HOST>/neondb?sslmode=require'
   deploy/neon_legal_backup.sh backup        # -> deploy/backups_neon/legal_<time>.sql
   ```
3. **Migrations 0021 + 0022** (0021: vector column of any dimension + one HNSW index per
   dimension, keeps the Gemini vectors, so the running Render service keeps working;
   0022: the per-organization query-rewrite cache table, unused by the old code):
   ```bash
   cd backend
   ALEMBIC_DATABASE_URL='postgresql+asyncpg://app_owner:<APP_OWNER_PW>@<HOST>/neondb?sslmode=require' \
     uv run alembic upgrade head            # ... -> 0022_query_rewrite_cache
   cd ..
   ```
4. **Dry run** (does everything in one transaction, then ROLLBACK; TRUNCATE-based, so it
   leaves no dead rows behind):
   ```bash
   REVIEWER_EMAIL='<your Neon account email>' DRY_RUN=1 deploy/neon_cutover_e5small.sh
   ```
   If that account does not exist in Neon yet, also set `REVIEWER_NAME='<your name>'`:
   it is then created as an active admin without a password. Expect
   `DRY RUN: every check passed`.
5. **Real run** (same command with `DRY_RUN=0`, about 30 s; search waits on the table lock
   meanwhile). Expect `approved_acts 1176 | sections 35063 | chunks 39587 |
   cited_chunks_no_longer_present 0 | rls_forced 38/38`, then `COMMITTED` and the database
   size (rehearsal: 307 MB; Neon free limit 0.5 GB). From here until step 6 is live, the
   old Render service answers search with `503 EMBEDDING_MODEL_MISMATCH` (it embeds with
   Gemini); keep this window short.
6. **Deploy**: merge `feat/full-corpus-e5small` into `deploy/render` and push. Render
   rebuilds the image (the build downloads and quantizes the model and fails unless it has
   the pinned SHA-256). In Render → Environment, delete `GEMINI_EMBEDDING_MODEL` (a
   Blueprint does not remove variables it no longer lists; it is ignored anyway).
7. **Smoke test** (section 7): the search line must say
   `embeddings intfloat/multilingual-e5-small`. Then delete `deploy/corpus_e5small/`.

### Rollback

No migration downgrade is needed: the pre-cutover code reads the 0021 column fine and
ignores the 0022 table
(rehearsed: old image + restored data passes the smoke test).

1. Render → the service → **Events** → previous deploy → **Rollback** (or push the previous
   `deploy/render` commit). Set `EMBEDDING_PROVIDER=gemini` and
   `GEMINI_EMBEDDING_MODEL=gemini-embedding-001` in Environment if you changed them.
2. `deploy/neon_legal_backup.sh restore deploy/backups_neon/legal_<time>.sql`: puts the
   19 Acts and their Gemini vectors back in one transaction (same ids, so analyses made
   before the cutover cite existing chunks; analyses made after it may cite chunks that no
   longer exist). The approval audit events and the reviewer account stay (history).
3. Smoke test: `embeddings gemini-embedding-001`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Render deploy fails, log says `DATABASE_URL must use postgresql+asyncpg as app_user` | URL must start `postgresql+asyncpg://app_user:` |
| `connect() got an unexpected keyword argument` | You are on an old commit; this branch translates `sslmode` |
| `/health/ready` is 503 | Wrong Neon password/host, or the `-pooler` host. Use the direct host |
| Search answers `503 NOT_CONFIGURED` | `GEMINI_API_KEY` missing/invalid, or the Gemini free-tier quota is used up (wait for the reset). Render → Logs shows `provider.unavailable` |
| Analysis findings labelled AI mock | Both Gemini models answered 429/503 (free-tier overload) through all retries, or the 100 s budget ran out. Render → Logs: `llm.fallback_to_mock`; the analysis warnings list each `provider_error:...@model`. Run it again later |
| Analysis shows "Keyword-only search" | Gemini embedding quota (1,000/day, 100/min on the free tier) is used up or the API is down; results are full-text only until it recovers. Not an error |
| Search answers `503 EMBEDDING_MODEL_MISMATCH` | The database holds vectors from another model than `EMBEDDING_PROVIDER`/`GEMINI_EMBEDDING_MODEL` (e.g. an old e5 dump). Rebuild the dump from a Gemini-embedded knowledge base (`deploy/make_demo_dump.sh` prints `Embeddings: gemini-embedding-001 v1`) and restore it into a fresh Neon database, or set the provider that matches the dump |
| Every POST answers 403 "Request origin is not allowed" | `APP_ORIGIN` differs between Render and Vercel (check `https`, no trailing `/`) |
| Upload answers 503 NOT_CONFIGURED | B2 values: endpoint must be a bare host, `MINIO_SECURE=true`, key limited to this bucket with Read and Write |
| Render Events show "Out of memory" | Set `OCR_DPI=200` in Render → Environment |
| First request very slow | Render free sleeps after 15 min; Neon pauses too. Normal |

## Switching the knowledge base between e5 and Gemini (local)

The vectors in the database and the query embedder must come from the same model
(`legal_chunks.embedding_model` / `embedding_version`, recorded per chunk). Search
checks this on every request and answers `503 EMBEDDING_MODEL_MISMATCH` otherwise,
so a half-converted database never returns silent garbage.

```bash
deploy/embeddings_backup.sh backup e5_20261121      # copy table + backups/embeddings_e5_20261121.dump
cd backend
uv run python -m app.rag.embed reembed --provider gemini --yes   # paced at 90 texts/min (free tier: 100)
# set EMBEDDING_PROVIDER=gemini in backend/.env, then rebuild the demo dump
```

The free tier counts every text in a batch as one request (100 per minute), so the
2652-chunk knowledge base takes about 30 minutes. `reembed` is resumable: if it is
interrupted, `uv run python -m app.rag.embed run --provider gemini` continues.

Roll back to e5 locally (no re-embedding, about a second):

```bash
deploy/embeddings_backup.sh restore e5_20261121
# set EMBEDDING_PROVIDER=local (or remove it) in backend/.env
```

How the 19-Act demo knowledge base was built (2026-11-21): the dev database was copied
to `legal_copilot_gemini` (dev stays e5), the partial Gemini vectors were restored
into the copy, every Act outside `deploy/demo_acts.txt` was deleted from the copy, the
remaining chunks were embedded (`LEGAL_INGEST_DATABASE_URL=.../legal_copilot_gemini
uv run python -m app.rag.embed run --provider gemini`), and the dump was built from it:
`SOURCE_DB=legal_copilot_gemini DEMO_LAWYER_PASSWORD=... deploy/make_demo_dump.sh`. The
dump script refuses a database with unembedded chunks or mixed models.

The e5 demo dump from before the switch is kept as `backups/demo_data_e5_20261121.dump`
(git-ignored).

## Measured results: full corpus on e5-small (local, 2026-11-22)

Neon-like Postgres 17 (non-superuser owner, app_owner without BYPASSRLS, RLS forced 38/38)
holding the demo dump, then `alembic upgrade head` (0020, 0021, 0022) and the cutover above;
`backend/Dockerfile.render` image in `docker run --memory=512m --memory-swap=512m`, local
MinIO, real Gemini LLM. Peak = cgroup `memory.peak`.

| Check | Result |
|---|---|
| Image | 1.77 GB on disk, about 456-478 MB compressed (was 1.49 GB / 364 MB); model files 129 MB, SHA-256 checked at build and at load |
| Database after cutover | 305-307 MB (`pg_database_size`; was 24 MB). Dry run leaves no bloat; re-running the cutover (also after 0022) stays at 306-307 MB |
| Cutover time | about 30 s (load, HNSW build, 1,176 approvals, checks) |
| Idle after start (query model preloaded) | 264-269 MiB, start-up peak 335-345 MiB |
| Smoke test (search + analysis + OCR upload) | ALL PASSED; search top hit NI Act s.138 (cosine 0.88) |
| 2-3 searches + 1 analysis + 1 OCR upload at once | **peak 392-438 MiB** (4 runs; with batched, cached rewrites) |
| Stress: 2 searches + 1 analysis + 2 OCR uploads at once | **peak 426-455 MiB** (4 runs, one above 450; no OOM; 501 MiB before `EXTRACTION_MAX_CONCURRENT=1`; the second upload waits about 1 s) |
| Search latency | 50-180 ms without rewriting (embedding about 5 ms); 3-7 s with rewriting: the Gemini call dominates |

What it took to fit 512 MB:
- **Tokenizer**: the `tokenizers` XLM-R model (250k pieces) costs about 285 MB of RAM. The query
  path uses the original `sentencepiece.bpe.model` (about 15 MB) instead: identical ids on
  all 98 eval queries and on 39,579 of 39,587 chunks (8 have two equal-score segmentations);
  ingestion and the embed worker keep `tokenizers`, so stored vectors stay reproducible.
- **ONNX Runtime**: graph optimization level EXTENDED instead of ALL. ALL pre-packs weights
  (RSS about 475 MB, load peak about 550 MB: OOM-killed on the first search); EXTENDED is
  about 185 MB with bit-identical vectors.
- **Preload**: `PRELOAD_QUERY_EMBEDDER=true` loads the model at start-up, so its one-time load
  peak never coincides with an OCR upload.

## Measured results (local, 2026-11-21)

### Memory (Render free = 512 MB)

`backend/Dockerfile.render` image run with `docker run --memory=512m`, one uvicorn
worker, against a Neon-like Postgres 17 holding the demo dump and local MinIO.
Peak = cgroup `memory.peak` (includes the Tesseract subprocess and page cache; the
1-second `docker stats` samples miss short OCR spikes and read lower).

| Scenario | OCR_DPI | Peak |
|---|---|---|
| Idle after start | | 118 MiB (docker stats 95 MiB) |
| Scanned A4 PDF, RGB rendering (before this branch) | 300 | **471 MiB (over budget)** |
| Same, greyscale rendering (this branch) | 300 / 250 / 200 | 182-293 MiB |
| 24 MP phone photo + 5-page scan, then 2 scans uploaded concurrently | 300 / 250 / 200 | 372 / 344 / 324 MiB |
| Smoke test with real Gemini search + analysis + OCR upload to MinIO, 19-Act Gemini dump (2026-11-21) | 250 | **208 MiB** (idle 117 MiB); 231 MiB after 2 more analyses |
| Same, first run (Gemini key mis-quoted, so labelled keyword-only fallback) | 250 | 376 MiB |

Greyscale OCR (Tesseract binarizes anyway) plus a pixel budget for photos removed
most of the memory; `OCR_DPI=250` is set for headroom. Bangla OCR accuracy on the
test page: 0.966 at 300 DPI, 0.974 at 250, 0.994 at 200.

### Smoke test against the Render image (local, 2026-11-21)

`docker run --memory=512m` of `backend/Dockerfile.render`, Postgres 17 with the 19-Act
Gemini dump restored like Neon (non-superuser owner, RLS forced 37/37), local MinIO,
real Gemini key:

```
[PASS] legal search: HTTP 200, 5 hits in 0.8s, mode hybrid, embeddings gemini-embedding-001,
       top: The Negotiable Instruments Act, 1881 s.138 (cosine 0.7337)
[PASS] case analysis: HTTP 201 in 3.8s, status succeeded, origin ai_mock (mock), 3 finding(s)
[PASS] OCR upload to B2: HTTP 201, ready, 1.6s
ALL PASSED
```

Analysis retrieval used Gemini (NI Act ss. 138, 84, 31, 136 at cosine 0.64-0.72, above
the 0.624 threshold; 3 verified findings), but the Gemini **LLM**
(`gemini-3.5-flash-lite`) answered `503 "This model is currently experiencing high
demand"` on all three runs, so the findings came from the labelled mock
(`origin ai_mock`, warning `provider_error:HTTPStatusError:503`). The smoke test only
requires `status succeeded`; it fails if search is not `mode hybrid`.

After the quote-repair change (same container, 2026-11-21, one live run): real Gemini
analysis in 4.9 s, `origin ai`, `gemini-3.5-flash-lite` on the first attempt; finding
NI Act s.138 **verified** with all 4 elements verified. Gemini had dropped the bdlaws
footnote markers ("3", "4", "5" on their own lines) from its quotes; the verifier matched
them (ratio 0.995-0.997) and stored the exact source spans. Peak 188 MiB.

### Gemini vs e5 retrieval

See `DOCS/eval_results.md` (19-Act subset): Gemini Recall@10 1.0 on both query sets
(e5 0.923 / 0.95); abstain threshold 0.624.
