# BatchHelm Vision Inspection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add shelf-photo upload and vision-inspection workflow so BatchHelm can inspect product labels, lot codes, UPCs, and recall match confidence.

**Architecture:** The backend receives multipart image uploads, validates and stores them locally, routes image bytes through the Qwen gateway when configured, and returns typed inspection results. The frontend adds a compact shelf-inspection panel that can upload an image to the backend and render the result while preserving local demo fallback behavior.

**Tech Stack:** FastAPI `UploadFile`, Pydantic v2, HTTPX, Qwen OpenAI-compatible image content, React, TypeScript.

---

## File Structure

- Modify `services/api/src/batchhelm_api/config.py` with `UPLOAD_DIR`.
- Modify `services/api/src/batchhelm_api/models.py` with inspection models.
- Modify `services/api/src/batchhelm_api/qwen.py` with image JSON completion support.
- Create `services/api/src/batchhelm_api/storage.py` for upload validation and local persistence.
- Modify `services/api/src/batchhelm_api/app.py` with inspection routes.
- Create `services/api/tests/test_storage.py` and `services/api/tests/test_inspection_api.py`.
- Modify `services/api/tests/test_qwen_gateway.py` for image payload tests.
- Modify `apps/web/src/api.ts`, `apps/web/src/App.tsx`, and `apps/web/src/styles.css` with shelf inspection upload UI.
- Modify `docs/qwen-integration.md` and `README.md` with the inspection endpoint.

### Task 1: Backend Inspection Models And Storage

**Files:**
- Modify: `services/api/src/batchhelm_api/config.py`
- Modify: `services/api/src/batchhelm_api/models.py`
- Create: `services/api/src/batchhelm_api/storage.py`
- Create: `services/api/tests/test_storage.py`

- [ ] **Step 1: Add upload settings and inspection models**

Add typed upload metadata, extracted label fields, and inspection result models.

- [ ] **Step 2: Implement upload storage**

Validate JPEG, PNG, and WebP files up to 8 MB, generate safe filenames, persist bytes under `UPLOAD_DIR`, and return metadata.

- [ ] **Step 3: Add storage tests**

Verify accepted image types, rejected file types, size limit, and safe filename generation.

### Task 2: Qwen Vision Gateway

**Files:**
- Modify: `services/api/src/batchhelm_api/qwen.py`
- Modify: `services/api/tests/test_qwen_gateway.py`

- [ ] **Step 1: Add image JSON completion**

Build a Qwen-VL payload with text and `image_url` content parts using a base64 data URL.

- [ ] **Step 2: Add fallback result**

When no key is configured, return a deterministic spinach label extraction result.

- [ ] **Step 3: Add gateway tests**

Mock provider responses and assert image payload shape, parsed JSON, and fallback behavior.

### Task 3: Inspection API Routes

**Files:**
- Modify: `services/api/src/batchhelm_api/app.py`
- Create: `services/api/tests/test_inspection_api.py`

- [ ] **Step 1: Add upload route**

Implement `POST /api/inspections/shelf-photo` for multipart image upload and typed inspection result.

- [ ] **Step 2: Add sample route**

Implement `GET /api/inspections/demo` returning the deterministic demo inspection result.

- [ ] **Step 3: Add route tests**

Verify upload success, rejected content type, demo route, and recall-match fields.

### Task 4: Frontend Inspection Panel

**Files:**
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/styles.css`

- [ ] **Step 1: Add upload client**

Post a shelf image to `/api/inspections/shelf-photo` and map the response to frontend state.

- [ ] **Step 2: Add UI panel**

Add a shelf inspection panel to the dashboard with file input, upload state, fallback message, and extracted product/lot/match result.

- [ ] **Step 3: Preserve responsive layout**

Keep the desktop command-center density and mobile collapse stable.

### Task 5: Docs, Verification, Push

**Files:**
- Modify: `README.md`
- Modify: `docs/qwen-integration.md`

- [ ] **Step 1: Document inspection endpoint**

Add endpoint, file limits, runtime modes, and Qwen-VL usage notes.

- [ ] **Step 2: Run verification**

Run backend tests, frontend build, and attribution-language scan.

- [ ] **Step 3: Commit and push**

Commit the completed slice and push `main`.

## Self-Review

- Spec coverage: Covers upload, storage, Qwen-VL gateway, API routes, frontend panel, docs, verification, and push.
- Placeholder scan: No unresolved placeholders remain.
- Type consistency: Inspection model names align across backend, API client, and UI.
