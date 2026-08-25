# Upload storage redesign — plan

Written for implementation in a later session. Do not implement from this file without
re-reading the current state of the code first — it may have moved on.

## Why

This session hit a chain of OOM/timeout incidents that all trace back to one root decision:
raw uploaded file bytes are stored as a `bytea` column value (`ingestion_jobs.payload`,
`documents.raw_file_bytes`) and processed fully in memory. Fixed so far, one symptom at a time:

1. a2wsgi/Werkzeug losing the request body when `Content-Length` is missing (`asgi_bridge.py`).
2. `DB_STATEMENT_TIMEOUT_MS_DEFAULT` too short for the `ingestion_jobs.payload` INSERT of a large
   file — worked around with a `SET LOCAL` override scoped to that one statement
   (`DB_STATEMENT_TIMEOUT_MS_LARGE_PAYLOAD_DEFAULT`, `ingestion_job_repository.py`).
3. API/worker pod memory limits too low for holding a large file + its parsed structures.
4. Worker's DB session idle-in-transaction timeout too short for a long parse/embed pipeline that
   doesn't touch the DB in between (`DB_IDLE_IN_TRANSACTION_TIMEOUT_MS` override on the worker).
5. `PdfSplitter.split()` materializing every split part into one list while the original file
   bytes were still held too — fixed with lazy `plan_for()`/`iter_parts()`.
6. `IngestionService._process()` holding every chunk's text and every embedding vector in memory
   at once for the whole document — fixed with batched embed/persist
   (`INGESTION_EMBED_BATCH_SIZE`) + `ChunkRepository.delete_for_document()` for retry-safety.
7. `PdfParser.parse()` never releasing pdfplumber's per-page cached object graph — fixed with an
   explicit `page.close()` per page.
8. **The one that forced this redesign**: a 109MB file's `INSERT` into `ingestion_jobs.payload`
   OOM-killed the *Postgres* container itself (1Gi limit), crashing the whole database into WAL
   recovery — not a failed upload, a full availability incident for every org during recovery.

Every one of those is a symptom of the same root cause: a file's raw bytes get fully materialized
in a Python process and/or a database row. Moving storage off both fixes the *class* of problem
instead of the next instance of it.

## Decision: local disk, not object storage

Considered S3/MinIO first (the generic "industry standard" answer) and talked it back down to a
**shared local volume**, because this deployment is genuinely single-node (one k3s node on one
Hostinger VPS, ~100GB disk headroom) — adding a new stateful service (MinIO, its own PVC, its own
backup story) solves a distributed-storage problem this deployment doesn't have yet. A local
volume gets the actual thing that matters — bytes out of Postgres, off the request/DB critical
path — with far less new infrastructure.

**Known limitation, must be documented in-repo when this lands (see "Second-node note" below):**
this only works because every pod runs on the same node. `ReadWriteOnce` allows multiple *pods* to
mount a volume as long as they're on the same *node* — it restricts to one node, not one pod. The
moment this cluster ever grows to a second node, a shared local volume stops working for any pod
scheduled onto the other node, and this needs to become networked storage (MinIO, NFS, real S3)
instead. Don't let that redesign get discovered the hard way like every fix above was — write it
down before it's needed, not after.

## Storage layout

```
<PVC mount root>/<org_id>/<ingestion_job_id>/upload.bin
```

- **`org_id`, not org slug/name** — this app already lets an admin rename an org (changes its
  slug, item 28 in this repo's CLAUDE.md session history); a path keyed on a mutable slug would
  break or need a bulk file-move on rename. The org UUID never changes.
- **`ingestion_job_id`** — guarantees uniqueness (no filename collisions across uploads), and
  scopes the file's lifetime to exactly the job that owns it. One file per job regardless of
  whether the job later splits into multiple documents — PDF splitting happens transiently in
  memory during processing from this one source file, not as separate files on disk.
- **Fixed filename (`upload.bin`), not the user's original filename** — the real filename is
  already tracked in `ingestion_jobs.payload_filename`; there's nothing to gain from also encoding
  it in the path, and it sidesteps sanitizing a user-supplied string for path safety entirely.
- **Cleanup**: once a job's document(s) reach `indexed`, delete the whole
  `<org_id>/<ingestion_job_id>/` directory in one shot — no per-file cleanup logic, matches "don't
  keep the file after indexed." A **failed** job's directory is *not* deleted (mirrors today's
  `raw_file_bytes`-kept-until-indexed behavior) — retry needs the file still on disk.

## Kubernetes changes

- New `PersistentVolumeClaim` (same `local-path` StorageClass Postgres already uses) — e.g.
  `knowledge-uploads-data`, sized generously (this is the ~100GB-disk argument the user made).
- Mounted at the same path (e.g. `/data/uploads`) in **both** `knowledge-api` and
  `knowledge-ingestion-worker` Deployments (`api/deploy/k3s/02-api.yaml`,
  `api/deploy/k3s/07-ingestion-worker.yaml`) — both pods already run on this cluster's one node, so
  RWO is sufficient (see "Known limitation" above).
- Likely lives in `api/deploy/k3s/` alongside `01-postgres.yaml` (api+db release artifact, not
  webui/cluster-shared) — new file, e.g. `01b-uploads-pvc.yaml`, or folded into `01-postgres.yaml`
  as a second PVC. Decide when implementing based on whichever reads more clearly.

## Database schema (new Alembic migration)

- `ingestion_jobs.payload` (`bytea`) → drop, replace with `payload_path` (`text`, nullable) —
  either the org-relative path (`<org_id>/<job_id>/upload.bin`) or the full mount-relative path;
  pick one convention and use it consistently everywhere it's read.
- `documents.raw_file_bytes` (`bytea`) → same treatment, or reconsider whether it's still needed
  at all once `ingestion_jobs.payload_path` already covers "keep the file for retry" — check
  `DocumentRepository.get_raw_bytes()`'s only caller (`IngestionService.retry()`) before deciding
  whether this column becomes redundant.
- Both existing bytea columns are effectively already-cleared/short-lived (nulled once indexed via
  `DocumentRepository.update_status()`), so this migration doesn't need a backfill — just add the
  new column(s), migrate write paths, then drop the old ones in the same or a fast-follow
  migration.

## Pipeline changes

- **`api/presentation/routes/documents.py`'s `upload_document()`**: replace `file_bytes =
  uploaded.read()` (reads the entire upload into one Python `bytes` object) with
  `uploaded.save(destination_path)` (Werkzeug's `FileStorage.save()` streams from the WSGI input in
  chunks straight to disk) — this is the other half of the memory win beyond "don't store bytes in
  Postgres": the **API pod** stops holding the whole file in memory too, not just the database.
  `destination_path` needs the job id up front, which means creating the `ingestion_jobs` row (to
  get its id) before the file is fully written — check whether `IngestionJobRepository.create()`
  needs to move earlier in the flow, or whether the id can be pre-generated client-side-of-the-DB
  (`uuid4()` in Python before `create()`) and passed in.
- **`api/ingestion_worker/worker.py`**: replace `payload = ingestion_jobs.get_payload(job.id)`
  (bytea fetch) with reading `job.payload_path` and opening that file.
- **`api/infrastructure/parsing/pdf_parser.py`**: `pdfplumber.open()` accepts a file path directly,
  not just a `BytesIO` — passing the path lets pdfplumber read directly from disk rather than
  requiring the caller to have already loaded the whole file into memory. Same idea for whichever
  other parsers in `api/infrastructure/parsing/` take `file_bytes` today
  (`ParserRegistry`/`api/infrastructure/parsing/registry.py`) — check each one's actual API for a
  path-accepting variant instead of assuming a blanket "read bytes first" pattern is fine.
- **`api/application/pdf_split_ingestion_service.py` / `pdf_splitter.py`**: `plan_for()`/
  `iter_parts()` currently take `file_bytes` — change to take a path (or a file handle) so the
  *source* PDF is read from disk too, not just written there. Split parts themselves can likely
  stay as in-memory `bytes` handed straight to `IngestionService.ingest()` per part (already lazy,
  already bounded to one part at a time) — no obvious need to also write parts to disk as
  intermediate files, but reconsider if a part turns out to still be large enough to matter.
- **Non-PDF parsers** (txt/md/html — `api/infrastructure/parsing/`): check whether each one
  actually benefits from path-based reading or whether "read the whole (usually small) file into
  memory" is fine for those types — the memory problem this session hit was specifically about
  large PDFs; don't over-engineer the path for content types that were never the issue.

## Refresh-safe progress tracking

Before building anything new here: `GET /ingestion-jobs` already exists and is already polled by
`RecentUploadsList.tsx`/`IngestionActivityTable.tsx` (`webui/src/api/queries.ts`'s
`useIngestionJobs()`). A page refresh re-mounts those components, which re-fetches from that same
endpoint — so job status *should* already survive a refresh today, since it's server-side state,
not client-only. **Verify this claim against the real deployed app before assuming new backend
work is needed** — the user's ask ("I need the progress clearly shown... even when we refresh the
page, because this is purely async now") may already be satisfied by what exists, or there may be
a real gap (e.g., no visible in-progress indicator on the page the user actually uploaded from,
only in the separate Recent Uploads list/Dashboard activity table). If there's a real gap, it's
almost certainly a frontend-only fix (surface the existing job-status polling more prominently on
the upload page itself), not a new backend endpoint.

## Resource limits — re-test, don't assume

Current state (all raised this session while chasing the bytea-in-Postgres problem):
`knowledge-api` 2Gi, `knowledge-ingestion-worker` 7Gi, `knowledge-db` 2Gi. Once this redesign lands,
re-test at lower limits (user's target: 2Gi/1 vCPU each) against real files, including a
deliberately large/complex one — this session's best real data point post-fixes was 351MB peak RSS
for a 4,706-chunk document, which is promising but is not the same as a verified guarantee.
`kubectl top pod` during a real large upload is the way to check, not assumption. Ratchet limits
down gradually and watch for `OOMKilled` in `kubectl describe pod`, the same way every limit in
this file's history was raised — evidence-based in both directions.

## Testing checklist (mirror this session's own pattern for each fix)

- Unit/integration test for the new path-based upload flow (a real small file through
  `upload_document()`, confirm the DB row's `payload_path` and confirm the file lands where
  expected).
- Regression test for retry-after-failure using the still-on-disk file (mirrors
  `test_retry_after_failure_succeeds` in `api/tests/integration/test_ingestion_service.py`, but
  reading from disk instead of a bytea column).
- Regression test proving an **indexed** job's directory is deleted, and a **failed** job's is not.
- Regression test for the PDF-split path reading its source from disk correctly (mirrors
  `api/tests/integration/test_pdf_split_ingestion.py`).
- Whatever frontend fix (if any) lands for progress-on-refresh should get a Playwright e2e case if
  this repo's webui test suite covers that flow already (`webui/tests/e2e/`) — check before adding
  a new pattern.
- Real end-to-end verification against the actual dev-preview or prod-like stack with a genuinely
  large (close to `MAX_REQUEST_BODY_MB`) file, not just synthetic small-file unit tests — every
  incident this session found was invisible to the existing small-fixture test suite and only
  surfaced against a real large file.

## Second-node note — write this into `docs/HOSTINGER_DEPLOY.md` or this repo's CLAUDE.md when implemented

Add an explicit, easy-to-find note (not buried) stating: the upload storage volume is
node-local and only works because this cluster is single-node today. Before ever adding a second
node to this cluster, this volume must be replaced with networked storage (MinIO is the leading
candidate — speaks the S3 API, self-hostable, minimal new operational surface vs. real cloud
object storage) or both the API and worker Deployments must be pinned to the same node via a
`nodeSelector`/`nodeAffinity` as a stopgap. Do not add a second node without addressing this first.
