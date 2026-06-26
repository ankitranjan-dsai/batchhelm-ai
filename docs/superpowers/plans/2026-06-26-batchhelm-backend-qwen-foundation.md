# BatchHelm Backend And Qwen Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested FastAPI backend that exposes BatchHelm recall incidents, runs a typed recall workflow, and includes a Qwen Cloud-ready model gateway with deterministic demo fallback.

**Architecture:** The API lives in `services/api` as a focused Python package with domain models, sample data, workflow services, provider gateway, and route modules. The backend is intentionally usable without a Qwen key for demos, while real Qwen calls are isolated behind environment-driven configuration.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, HTTPX, pytest, uv.

---

## File Structure

- Create `services/api/pyproject.toml` for backend dependencies, scripts, and pytest settings.
- Create `services/api/src/batchhelm_api/config.py` for environment-driven configuration.
- Create `services/api/src/batchhelm_api/models.py` for domain and API contracts.
- Create `services/api/src/batchhelm_api/sample_data.py` for a synthetic spinach recall scenario.
- Create `services/api/src/batchhelm_api/qwen.py` for Qwen Cloud chat/vision gateway and fallback outputs.
- Create `services/api/src/batchhelm_api/workflow.py` for recall analysis, task generation, evidence packet state, and memory insights.
- Create `services/api/src/batchhelm_api/app.py` for FastAPI app factory and routes.
- Create `services/api/src/batchhelm_api/__init__.py` for package exports.
- Create `services/api/tests/test_workflow.py`, `services/api/tests/test_qwen_gateway.py`, and `services/api/tests/test_api.py`.
- Create `docs/qwen-integration.md` for Qwen setup and operational notes.
- Modify `README.md` with backend run and verification commands.

### Task 1: Backend Package Scaffold

**Files:**
- Create: `services/api/pyproject.toml`
- Create: `services/api/src/batchhelm_api/__init__.py`

- [ ] **Step 1: Create backend package metadata**

Add FastAPI, Uvicorn, Pydantic Settings, HTTPX, and pytest dependencies.

- [ ] **Step 2: Create package init**

Export the package version from `services/api/src/batchhelm_api/__init__.py`.

- [ ] **Step 3: Install backend dependencies**

Run: `uv sync --extra dev` from `services/api`.

- [ ] **Step 4: Commit**

Run:

```bash
git add services/api/pyproject.toml services/api/src/batchhelm_api/__init__.py
git commit -m "chore: scaffold BatchHelm API service"
```

### Task 2: Domain Models And Workflow

**Files:**
- Create: `services/api/src/batchhelm_api/models.py`
- Create: `services/api/src/batchhelm_api/sample_data.py`
- Create: `services/api/src/batchhelm_api/workflow.py`
- Create: `services/api/tests/test_workflow.py`

- [ ] **Step 1: Define typed domain models**

Add models for recall criteria, inventory rows, workflow events, tasks, evidence items, memory insights, agent activity, customer notice draft, and incident analysis.

- [ ] **Step 2: Add synthetic sample incident**

Create the spinach lot-code scenario with supplier aliases, inventory rows, and recall notice text.

- [ ] **Step 3: Implement deterministic workflow**

Implement lot matching, affected inventory decisions, evidence progress, generated tasks, memory insights, agent activity, and customer notice draft.

- [ ] **Step 4: Add workflow tests**

Assert affected lot matching, task creation, evidence progress, and notice content.

- [ ] **Step 5: Commit**

Run:

```bash
uv run pytest tests/test_workflow.py -q
git add services/api/src/batchhelm_api/models.py services/api/src/batchhelm_api/sample_data.py services/api/src/batchhelm_api/workflow.py services/api/tests/test_workflow.py
git commit -m "feat: add recall workflow engine"
```

### Task 3: Qwen Gateway

**Files:**
- Create: `services/api/src/batchhelm_api/config.py`
- Create: `services/api/src/batchhelm_api/qwen.py`
- Create: `services/api/tests/test_qwen_gateway.py`

- [ ] **Step 1: Add environment settings**

Load `QWEN_API_KEY`, `QWEN_BASE_URL`, `QWEN_TEXT_MODEL`, `QWEN_VISION_MODEL`, `APP_ENV`, and `LOG_LEVEL`.

- [ ] **Step 2: Implement gateway contracts**

Add a `QwenGateway` that can classify provider availability, build chat-completion payloads, parse JSON content, and return typed fallback data when no key is configured.

- [ ] **Step 3: Add gateway tests**

Mock HTTPX responses and verify payload shape, header handling, parsed JSON, and no-key fallback behavior.

- [ ] **Step 4: Commit**

Run:

```bash
uv run pytest tests/test_qwen_gateway.py -q
git add services/api/src/batchhelm_api/config.py services/api/src/batchhelm_api/qwen.py services/api/tests/test_qwen_gateway.py
git commit -m "feat: add Qwen gateway abstraction"
```

### Task 4: FastAPI Routes

**Files:**
- Create: `services/api/src/batchhelm_api/app.py`
- Create: `services/api/tests/test_api.py`

- [ ] **Step 1: Implement app factory and routes**

Add `/health`, `/api/incidents/demo`, `/api/incidents/demo/analyze`, `/api/qwen/status`, and `/api/notices/customer-draft`.

- [ ] **Step 2: Add structured error handling**

Return JSON errors with `code`, `message`, and optional `details`.

- [ ] **Step 3: Add API tests**

Use FastAPI `TestClient` to verify health, demo incident, analysis workflow, provider status, and customer notice draft.

- [ ] **Step 4: Commit**

Run:

```bash
uv run pytest -q
git add services/api/src/batchhelm_api/app.py services/api/tests/test_api.py
git commit -m "feat: expose recall workflow API"
```

### Task 5: Documentation And Verification

**Files:**
- Create: `docs/qwen-integration.md`
- Create: `scripts/check-attribution.sh`
- Modify: `README.md`

- [ ] **Step 1: Document Qwen configuration**

Explain required environment variables, local demo fallback, and how Qwen text and vision models are intended to be used.

- [ ] **Step 2: Document backend run commands**

Add API install, test, and run commands to `README.md`.

- [ ] **Step 3: Run verification**

Run:

```bash
uv run pytest -q
cd ../../apps/web && npm run build
```

- [ ] **Step 4: Add and run attribution-language scan**

Run:

```bash
scripts/check-attribution.sh
```

Expected: no matches.

- [ ] **Step 5: Commit and push**

Run:

```bash
git add README.md docs/qwen-integration.md scripts/check-attribution.sh
git commit -m "docs: add Qwen backend integration guide"
git push
```

## Self-Review

- Spec coverage: The plan covers the API layer, Qwen gateway, workflow engine, structured errors, configuration, docs, tests, and push requirement.
- Placeholder scan: No TBD markers or undefined implementation steps remain.
- Type consistency: Route names, module names, and model names align across tasks.
