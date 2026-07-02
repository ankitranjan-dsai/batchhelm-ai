# Durable Incident Intake Design

**Status:** Architecture approved on 2026-07-02

## Purpose

BatchHelm currently starts its durable agent workflow from one bundled,
fully-structured demo incident. The product needs a canonical path from
ambiguous real-world evidence to that same durable workflow.

This milestone adds a restart-safe intake workspace that accepts a recall
notice, inventory export, and optional shelf photo; extracts and normalizes a
draft incident; exposes field-level provenance and confidence for human review;
and launches the existing nine-agent DAG only after confirmation.

## Goals

- Accept a recall notice as PDF, plain text, JPEG, PNG, or WebP.
- Accept inventory as CSV.
- Accept one optional shelf photo as JPEG, PNG, or WebP.
- Persist every intake, artifact, extraction result, correction, and confirmed
  incident snapshot in SQLite.
- Preserve original artifacts using generated names and SHA-256 fingerprints.
- Use Qwen text and vision models for structured extraction when configured.
- Never fabricate safety-critical fields when Qwen is unavailable or output is
  invalid.
- Require human confirmation before an intake can start an orchestration run.
- Launch and recover the existing durable DAG with the confirmed incident and
  real shelf artifact.
- Provide a polished Files -> Review -> Launch workflow in the dashboard.
- Keep the bundled demo flow available for deterministic testing and fallback
  demonstrations.

## Non-Goals

- Receiving mail directly from Gmail, Outlook, IMAP, or webhook providers.
- Processing arbitrary email mailbox history.
- A multi-incident queue or organization-wide recall inbox.
- Editing thousands of inventory rows individually in the browser.
- General-purpose OCR across unlimited pages.
- Authentication, RBAC, or multi-tenant data isolation.
- Multi-replica intake worker coordination.
- Replacing SQLite with Postgres in this milestone.

## Selected Approach

Three approaches were considered.

### One-shot multipart orchestration

The browser uploads files and the API immediately starts a run.

This is the smallest implementation, but it has no durable review boundary,
poor reconnect behavior, and no stable place for provenance or corrections. It
does not demonstrate a credible human-in-the-loop workflow.

### Durable intake workspace

The browser creates an idempotent persisted intake, the service extracts a
draft in the background, the operator reviews evidence-backed fields, and a
confirmed immutable snapshot starts the run.

This is the selected design. It reuses BatchHelm's repository and lifecycle
patterns, makes ambiguous input explainable, and remains achievable within the
hackathon schedule.

### Email-native ingestion

The product receives `.eml` files or mailbox webhooks and discovers
attachments automatically.

This is a valuable later milestone, but it introduces provider authentication,
message deduplication, mailbox security, attachment routing, and operational
infrastructure that are independent of the core intake problem.

## User Experience

### Entry point

The dashboard adds a visible `New recall` command using a file-plus icon and
text. It opens a full-height intake workspace rather than a new marketing page.
The existing dashboard remains visible behind the workspace, and an operator
can close an unconfirmed intake without affecting the current incident.

### Stage 1: Files

The Files stage contains three stable upload controls:

- Recall notice (required)
- Inventory CSV (required)
- Shelf photo (optional)

Each control shows the selected filename, media type, size, and validation
state. The primary `Process files` command is disabled until the two required
artifacts pass client validation. Upload progress and extraction status use
dedicated loading states; the interface does not imply that a run has started.

### Stage 2: Review

The Review stage has two coordinated areas:

- An editable incident form for product, affected lots, UPCs, risk, reason, and
  source.
- An inventory import summary with accepted row count, rejected row count,
  normalized header mappings, store count, and a bounded row preview.

Every extracted incident field shows:

- source artifact name;
- page or text locator where available;
- extraction source (`qwen`, `deterministic`, or `reviewer`);
- confidence;
- whether confirmation is required.

Manual edits create new reviewer provenance records instead of overwriting the
original extraction evidence. The operator can return to Files and replace the
packet before confirmation.

### Stage 3: Launch

The Launch stage summarizes the immutable snapshot:

- product and affected criteria;
- imported stores and inventory rows;
- optional shelf artifact;
- unresolved warnings;
- provider mode.

`Confirm and run agents` is disabled until all blocking fields and inventory
requirements pass validation. Confirmation freezes the snapshot, starts one
idempotent orchestration run, closes the workspace, and binds the dashboard and
Mission Control to that run.

### Responsive behavior

On desktop, Files and Review use a two-column working surface with a fixed
action footer. On mobile, controls stack into one column and the footer remains
reachable without covering content. Long filenames wrap, tables become
horizontally scrollable within their own region, and no control changes the
page width.

## Domain Model

### Intake status

`IntakeStatus` is a string enum:

- `uploaded`: artifacts are durable and waiting for extraction;
- `extracting`: one local worker owns extraction;
- `review_required`: a draft exists but one or more blocking fields require
  confirmation or correction;
- `ready`: the operator confirmed an immutable incident snapshot;
- `run_started`: an orchestration run has been created for the snapshot;
- `failed`: extraction could not produce a reviewable draft.

An intake cannot move backwards from `ready` or `run_started`. Replacing files
before confirmation creates a new intake request rather than mutating artifact
history.

### Artifact roles

`IntakeArtifactRole` is one of:

- `recall_notice`;
- `inventory_csv`;
- `shelf_photo`.

`IntakeArtifact` contains:

- `id`;
- `intake_id`;
- `role`;
- original filename;
- generated stored filename;
- media type;
- size;
- SHA-256 digest;
- relative storage path;
- creation timestamp.

Absolute filesystem paths are repository internals and never appear in public
API responses.

### Draft

`RecallIncidentDraft` contains:

- product;
- affected lots;
- UPCs;
- risk level;
- reason;
- source;
- normalized notice text;
- normalized inventory rows;
- stores derived from inventory;
- import warnings;
- optional shelf inspection;
- whether review is required.

The draft is separate from `RecallIncidentInput`. It may contain missing
required values while extraction is incomplete or uncertain.

### Provenance

`IntakeFieldEvidence` contains:

- stable evidence ID;
- field path such as `criteria.affected_lots`;
- JSON value;
- artifact ID;
- locator such as `page 2`, `line 18`, or `inventory row 42`;
- source (`qwen`, `deterministic`, or `reviewer`);
- confidence from 0 to 100;
- `requires_review`;
- optional ID of the evidence record it supersedes;
- creation timestamp.

Evidence is append-only. The current draft is the fold of evidence records in
creation order, with reviewer evidence taking precedence over extraction
evidence for the same field.

### Confirmed snapshot

Confirmation compiles a valid `RecallIncidentInput` and stores its canonical
JSON as an immutable snapshot. It uses:

- a generated incident ID scoped to the intake;
- `active` status;
- an ISO-8601 `opened_at` timestamp;
- sorted unique stores from valid inventory rows;
- a human-readable lot range derived from confirmed affected lots;
- the confirmed notice text, criteria, and normalized inventory.

The intake repository resolves a confirmed incident by incident ID for
orchestration start and restart recovery.

### Resolved run input

`ResolvedRunInput` is an internal immutable value containing:

- confirmed `RecallIncidentInput`;
- optional shelf artifact metadata;
- optional shelf image bytes;
- optional shelf image media type.

It is not serialized into the orchestration event database. The orchestration
run stores the incident ID; a resolver loads the immutable incident snapshot
and optional artifact from the intake repository when a worker starts or
recovers.

The bundled demo incident is handled by the same resolver boundary and returns
no real shelf artifact.

## Upload Policy

### Recall notice

Allowed media types:

- `application/pdf`;
- `text/plain`;
- `image/jpeg`;
- `image/png`;
- `image/webp`.

Limits:

- maximum 12 MB;
- maximum 10 PDF pages;
- maximum 100,000 normalized text characters;
- encrypted PDFs are rejected.

### Inventory

Allowed media type:

- `text/csv`, including UTF-8 with an optional byte-order mark.

Limits:

- maximum 4 MB;
- maximum 5,000 data rows;
- maximum 128 columns;
- NUL bytes are rejected.

### Shelf photo

Allowed media types:

- `image/jpeg`;
- `image/png`;
- `image/webp`.

Limit:

- maximum 8 MB.

### Packet

The total accepted packet size is 24 MB. Client-provided media types are
checked against file signatures for PDF and images. CSV and text content must
decode as UTF-8 or UTF-8 with a byte-order mark. Original path components are
discarded.

Artifacts are written under:

`UPLOAD_DIR/intakes/{intake_id}/{artifact_id}.{extension}`

The service writes to a staging location and uses an atomic rename after
validation. Database metadata is committed only for the final generated path.
Failed creation cleans its staging directory.

## Extraction Pipeline

### Notice parser

The notice parser produces `ParsedNotice` with normalized text, page count,
parse warnings, and page-level text locators.

- Plain text is normalized directly.
- Text-based PDFs use `pypdf`.
- If a PDF has fewer than 200 non-whitespace characters across the first three
  pages, those pages are treated as scanned evidence.
- Scanned pages are rendered with `pypdfium2` at a bounded resolution.
- Image notices use their original bytes.

PDF processing inspects content-stream size before text extraction and enforces
the page and character limits to prevent unbounded memory use.

### Qwen extraction

Text notices call the existing structured text gateway with an intake-specific
schema. Image notices and rendered scanned pages call the vision gateway.

For scanned PDFs, at most the first three pages are sent to Qwen, one bounded
request per page. Extraction stops early when all required fields have
confidence of at least 80. Results are merged by normalized value and retain
page-level provenance.

The extraction schema contains:

- product name;
- affected lots;
- UPCs;
- risk level;
- reason;
- supplier or issuing source;
- summary;
- confidence per field.

Model output is validated with Pydantic. Invalid shapes, provider failures, and
timeouts do not create fabricated field values.

### Deterministic safe extraction

When Qwen is unavailable or invalid, a deterministic parser may retain only
values found verbatim in the notice:

- lot-like tokens;
- UPC-like numeric tokens;
- the first non-empty heading as a product candidate;
- explicit risk words;
- explicit issuing-source lines.

These values are capped at 65 confidence and always require review. Missing
values remain empty. Demo-specific criteria are never copied into a real
intake.

### Inventory parser

The CSV parser uses Python's structured CSV reader. Header names are
case-insensitive and normalized for spaces, hyphens, and underscores.

Recognized aliases map to:

- store;
- SKU;
- product;
- lot;
- UPC;
- on-hand quantity;
- location;
- supplier alias.

`store`, `product`, `lot`, and `on_hand` are required. Missing optional values
become empty strings and are surfaced in import warnings; they do not become
safety criteria. Quantities must be non-negative integers. Duplicate rows with
the same store, SKU, lot, and location are rejected rather than silently
summed.

Invalid rows are omitted from the normalized inventory and reported with row
number and a sanitized reason. Confirmation requires at least one valid row.

### Shelf inspection

The optional shelf photo is retained as an intake artifact. After recall
criteria exist, the existing Qwen vision inspection runs against those criteria
and stores its result in the draft.

The current demo inspection fallback must not be reused for an uploaded intake
photo because it copies active recall values into the image result. For a real
photo, provider failure returns empty extracted label fields,
`recall_match = null`, and `review_required = true`. The result model therefore
represents recall match as `true`, `false`, or `null` (unknown). The seeded
positive fallback remains limited to the explicit demo inspection endpoint.

The artifact itself, not only the inspection result, remains available to the
orchestration resolver. `ShelfVisionAgent` therefore receives the uploaded
bytes and metadata on both initial execution and restart recovery. It must not
fall back to `demo-image` for an intake-backed run.

## Persistence

### Configuration

Add:

`INTAKE_DATABASE_PATH=./data/intake.db`

The API container uses:

`INTAKE_DATABASE_PATH=/data/intake.db`

### SQLite repository

`SQLiteIntakeRepository` uses WAL mode, foreign keys, a schema version, and
short transactions. It implements a typed `IntakeRepository` protocol.

Tables:

- `intakes`: lifecycle status, request ID, packet fingerprint, provider mode,
  version, timestamps, draft JSON, snapshot JSON, incident ID, run ID, and
  sanitized failure data;
- `intake_artifacts`: immutable role, filename metadata, size, digest, relative
  path, and timestamp;
- `intake_field_evidence`: append-only field provenance and supersession links.

`request_id` is unique. Reusing the same request ID with the same packet
fingerprint returns the existing intake. Reusing it with different artifacts
returns an idempotency conflict.

Draft updates use `expected_version`. A stale version returns a conflict and
does not overwrite newer reviewer changes.

### Intake lifecycle service

`IntakeService` owns one in-process extraction worker per intake.

On create:

1. validate and stage all artifacts;
2. calculate artifact digests and a canonical packet fingerprint;
3. resolve an existing idempotency key before changing final storage;
4. atomically move the staged intake directory to its final generated path;
5. insert the intake and artifact metadata in one database transaction;
6. clean the final directory if the database transaction loses a concurrent
   idempotency race or fails;
7. schedule extraction;
8. return the accepted intake view.

Startup removes generated intake directories that have no matching repository
record. A crash after the database transaction is recoverable because all
referenced files were already atomically moved into final storage.

The response is HTTP 202. The frontend polls the status URL while status is
`uploaded` or `extracting`.

On API startup, the service lists `uploaded` and `extracting` records, verifies
their artifacts, and restarts extraction. Duplicate starts never create
duplicate workers.

Extraction writes a complete draft and evidence records before changing status
to `review_required`. A non-recoverable parse failure changes status to
`failed` with a sanitized public code and message.

This worker model remains single-process. Multi-replica claims and leases are a
future Postgres milestone.

## API Contract

### Create intake

`POST /api/intakes`

Multipart fields:

- `request_id`: UUID string;
- `notice`: required file;
- `inventory`: required file;
- `shelf_photo`: optional file.

Response: HTTP 202 `IntakeAccepted`

- intake ID;
- status;
- status URL;
- created timestamp.

### Read intake

`GET /api/intakes/{intake_id}`

Response: `IntakeView`

- lifecycle and version;
- provider mode;
- public artifact metadata;
- draft when available;
- field evidence;
- import summary and warnings;
- confirmed incident ID when ready;
- orchestration run ID when started;
- sanitized failure information.

### Update draft

`PATCH /api/intakes/{intake_id}/draft`

JSON body:

- request ID;
- expected version;
- editable incident criteria fields;
- normalized inventory rows when corrections are required.

The request is idempotent. It appends reviewer evidence for changed criteria,
revalidates the draft, increments the version once, and returns the new
`IntakeView`.

### Confirm intake

`POST /api/intakes/{intake_id}/confirm`

JSON body:

- request ID;
- expected version.

Confirmation validates required fields and valid inventory, compiles the
immutable incident snapshot, changes status to `ready`, and returns the updated
view. Replaying the same request is safe.

### Start run

`POST /api/intakes/{intake_id}/runs`

JSON body:

- request ID.

Only a `ready` or already `run_started` intake is accepted. The service resolves
the immutable run input, starts one durable run, stores the run ID, changes
status to `run_started`, and returns `OrchestrationRunAccepted`. Replaying the
same request returns the same run.

Existing demo endpoints remain available and are marked as demonstration
contracts.

## Orchestration Integration

`OrchestrationService` changes from accepting only
`RecallIncidentInput` to accepting an internal `ResolvedRunInput`.

The service passes:

- `run_input.incident` to every agent;
- shelf image bytes and media type to `Orchestrator.run`;
- shelf upload metadata into the orchestration blackboard.

Restart recovery changes from one `build_demo_incident` factory to an incident
resolver:

`resolve_run_input(incident_id) -> ResolvedRunInput | None`

The application resolver:

1. returns the bundled demo incident for the demo incident ID;
2. asks `IntakeRepository` for an immutable intake snapshot and optional shelf
   artifact for other IDs;
3. returns `None` when no immutable source exists.

A missing or corrupt source fails the run with the sanitized
`incident_unavailable` code. Completed runs continue to serve their terminal
result directly from the orchestration database.

## Error Contract

All intake errors use the existing `APIError` envelope.

- HTTP 400 `invalid_upload`: malformed multipart data, unsupported encoding, or
  an unreadable file.
- HTTP 404 `intake_not_found`: unknown intake ID.
- HTTP 409 `idempotency_conflict`: a request ID was reused for different
  content.
- HTTP 409 `intake_state_conflict`: an operation is invalid for the current
  lifecycle state.
- HTTP 409 `intake_version_conflict`: reviewer data was based on a stale
  version.
- HTTP 413 `upload_too_large`: a file or packet exceeds its limit.
- HTTP 422 `intake_validation_failed`: confirmation has blocking fields or no
  valid inventory rows.
- HTTP 503 `intake_store_unavailable`: the intake repository or artifact store
  is unavailable.
- HTTP 500 `intake_processing_failed`: extraction failed without exposing
  provider, parser, filesystem, or database internals.

Row-level CSV problems are warnings in a reviewable draft. They are not HTTP
errors unless the file has no valid rows.

## Security And Privacy

- Qwen credentials remain environment-only.
- Filenames are display metadata and never filesystem paths.
- File signatures are checked before parsing.
- ZIP archives, executable formats, macros, and embedded attachments are not
  accepted.
- Parsing is bounded by bytes, pages, columns, rows, and normalized characters.
- Raw document text, inventory rows, and image bytes are excluded from logs.
- Structured logs include intake ID, artifact role, byte count, digest prefix,
  status transition, provider mode, and elapsed time.
- Public errors never include absolute paths, SQL details, provider payloads,
  or extracted document contents.
- Confirmed snapshots and evidence are immutable audit material.

## Frontend State

The intake workspace uses a reducer with:

- accepted intake metadata;
- current stage;
- upload progress;
- latest `IntakeView`;
- local editable draft;
- dirty-field tracking;
- validation errors;
- polling state;
- launch state;
- sanitized error message.

The reducer ignores stale intake versions and duplicate poll responses. Closing
the workspace stops polling but does not cancel server extraction. Reopening a
known intake restores its persisted state.

The current orchestration hook gains an explicit `adoptRun` operation. It
stores an `OrchestrationRunAccepted` returned by the intake run endpoint,
closes any prior event source, resets sequence state, and connects Mission
Control to the intake-backed run without creating a demo run.

React Strict Mode must not duplicate intake creation, confirmation, launch, or
event-source connections.

## Testing Strategy

### Backend unit tests

- file signature, media type, encoding, size, page, row, and character limits;
- text notice normalization;
- text PDF extraction;
- scanned PDF detection and bounded rendering;
- safe deterministic extraction with no demo-derived values;
- CSV header aliases, BOM handling, invalid rows, duplicate rows, and limits;
- draft validation and snapshot compilation;
- field evidence folding and reviewer precedence.

### Repository tests

- schema initialization and restart persistence;
- artifact and evidence ordering;
- identical create request reuse;
- conflicting create request rejection;
- optimistic version conflict;
- idempotent update, confirmation, and run linkage;
- recoverable intake listing;
- sanitized unavailable-store errors.

### Service tests

- one extraction worker per intake;
- disconnect does not cancel extraction;
- startup resumes `uploaded` and `extracting` records;
- extraction persists draft before status;
- Qwen failure produces reviewable, non-fabricated fields;
- confirmation freezes an immutable snapshot;
- launch creates exactly one orchestration run;
- shelf bytes and metadata survive run restart recovery.

### API tests

- successful text, PDF, image, CSV, and optional shelf multipart requests;
- structured 400, 404, 409, 413, 422, and 503 responses;
- status polling contract;
- reviewer update and confirmation contracts;
- start-run state and idempotency contracts;
- existing demo endpoints remain compatible.

### Frontend tests

- reducer stage and version behavior;
- upload validation;
- status polling and reconnect;
- review edits and validation;
- confirmation and run adoption;
- Strict Mode action deduplication;
- accessible keyboard and focus behavior.

### Browser verification

At desktop and mobile widths:

1. open New Recall;
2. upload the sample PDF, inventory CSV, and shelf photo;
3. observe extraction progress;
4. correct one low-confidence field;
5. inspect provenance and inventory warnings;
6. confirm and launch;
7. verify Mission Control uses the new incident and uploaded shelf artifact;
8. reload during extraction and during orchestration;
9. verify no duplicate intake or run;
10. verify no overflow, overlap, blank states, or console errors.

## Sample Data

Add deterministic, license-safe fixtures:

- `sample-data/recall-notice-spinach.pdf`;
- `sample-data/inventory-spinach.csv`;
- `sample-data/store-b-cooler-spinach.png`.

The notice and CSV describe the same existing spinach scenario so judges can
compare real intake with the bundled demonstration. A second malformed CSV
fixture exercises warning and review behavior.

## Deployment

Add `INTAKE_DATABASE_PATH` to `.env.example`, Dockerfile, Compose, and Alibaba
Cloud deployment documentation. The existing `/data` volume stores:

- intake database;
- intake artifacts;
- orchestration database;
- memory database;
- review ledger.

The API remains one replica while SQLite repositories and in-process workers
own lifecycle tasks.

## Documentation And Demo

Update:

- README API and workflow sections;
- architecture diagram and data flow;
- Qwen integration documentation;
- Alibaba Cloud persistence paths;
- known limitations;
- submission checklist;
- demo script.

The final demo must visibly show:

- real files entering the product;
- Qwen or deterministic source badges;
- a low-confidence field being reviewed;
- immutable confirmation;
- one intake-backed durable run;
- the real shelf photo in the Shelf Vision Agent;
- evidence and management outputs derived from the uploaded packet.

## Acceptance Criteria

The milestone is complete only when all of these are proven:

- One request ID creates one durable intake.
- Restart preserves artifacts, draft, evidence, corrections, and status.
- Text PDF, scanned PDF, image notice, plain text notice, and CSV paths are
  covered.
- No arbitrary intake fallback copies demo product, lot, UPC, supplier, or risk
  values.
- Provider failure cannot turn an uploaded shelf image into a fabricated
  positive recall match.
- Every confirmed safety-critical field has extraction or reviewer provenance.
- A stale reviewer version cannot overwrite a newer correction.
- An intake cannot launch before confirmation.
- Confirmation produces an immutable valid `RecallIncidentInput`.
- One launch request creates one durable orchestration run.
- Restart recovery resolves the same incident and optional shelf artifact.
- Shelf Vision Agent does not use the demo image for an intake-backed run.
- Existing durable event replay and wave recovery still pass.
- Backend, frontend, attribution, and Docker CI checks pass.
- Desktop and mobile end-to-end verification passes.
- Public documentation distinguishes real intake from the bundled demo.
