# BatchHelm Review Trail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reviewer approval gate and audit timeline for evidence packets so BatchHelm demonstrates controlled compliance release, not only packet generation.

**Architecture:** Add typed review models and a focused `review_trail.py` service that builds deterministic demo review state from the generated packet and recall analysis. Expose a preview route plus a decision route, then connect the dashboard Evidence panel to show readiness, blockers, reviewer actions, and immutable-style timeline events.

**Tech Stack:** FastAPI, Pydantic v2, pytest, React, TypeScript, Vite, existing CSS design system.

---

## File Structure

- Modify: `services/api/src/batchhelm_api/models.py`
  - Adds review status enums, checklist items, events, state, and decision request/response models.
- Create: `services/api/src/batchhelm_api/review_trail.py`
  - Owns demo review-state construction and decision projection.
- Modify: `services/api/src/batchhelm_api/app.py`
  - Adds `/api/evidence/demo-review` and `/api/evidence/demo-review/decision`.
- Create: `services/api/tests/test_review_trail.py`
  - Verifies review readiness, blockers, timeline content, and API decision behavior.
- Modify: `apps/web/src/types.ts`
  - Adds dashboard review-state types.
- Modify: `apps/web/src/api.ts`
  - Adds review-state fetch and decision helpers.
- Modify: `apps/web/src/App.tsx`
  - Adds review state loading, decision actions, and audit timeline UI inside the Evidence panel.
- Modify: `apps/web/src/styles.css`
  - Adds compact review gate and timeline styling.
- Modify: `README.md`
  - Documents the review endpoints and demo workflow.

## Task 1: Backend Review Models And Service

**Files:**
- Modify: `services/api/src/batchhelm_api/models.py`
- Create: `services/api/src/batchhelm_api/review_trail.py`
- Create: `services/api/tests/test_review_trail.py`

- [ ] **Step 1: Write service tests**

```python
from batchhelm_api.evidence_packet import build_demo_shelf_inspection, build_evidence_packet
from batchhelm_api.review_trail import build_demo_review_state, apply_review_decision
from batchhelm_api.sample_data import build_demo_incident
from batchhelm_api.workflow import analyze_recall_incident


def test_demo_review_state_marks_packet_not_ready_until_blockers_resolved() -> None:
    incident = build_demo_incident()
    analysis = analyze_recall_incident(incident)
    packet = build_evidence_packet(
        incident=incident,
        analysis=analysis,
        inspection=build_demo_shelf_inspection(),
    )

    state = build_demo_review_state(incident=incident, analysis=analysis, packet=packet)

    assert state.incident_id == "recall-spinach-2026-06"
    assert state.status == "needs-changes"
    assert state.ready_to_submit is False
    assert state.blocker_count == 2
    assert state.checklist[0].label == "Recall initiation report attached"
    assert "disposal" in state.next_action.lower()


def test_apply_review_decision_projects_approval_timeline() -> None:
    incident = build_demo_incident()
    analysis = analyze_recall_incident(incident)
    packet = build_evidence_packet(
        incident=incident,
        analysis=analysis,
        inspection=build_demo_shelf_inspection(),
    )

    state = apply_review_decision(
        incident=incident,
        analysis=analysis,
        packet=packet,
        reviewer="Operations Manager",
        decision="approved",
        note="Approved for supplier submission.",
    )

    assert state.status == "approved"
    assert state.ready_to_submit is True
    assert state.timeline[-1].actor == "Operations Manager"
    assert state.timeline[-1].title == "Packet Approved"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/api && uv run pytest tests/test_review_trail.py -q`

Expected: FAIL because `batchhelm_api.review_trail` does not exist.

- [ ] **Step 3: Add models**

Add these Pydantic models to `models.py`:

```python
class ReviewStatus(str, Enum):
    pending = "pending"
    needs_changes = "needs-changes"
    approved = "approved"


class ReviewChecklistStatus(str, Enum):
    passed = "passed"
    attention = "attention"
    blocked = "blocked"


class ReviewChecklistItem(BaseModel):
    id: str
    label: str
    status: ReviewChecklistStatus
    detail: str


class ReviewTimelineEvent(BaseModel):
    id: str
    title: str
    detail: str
    actor: str
    at: str
    status: ReviewStatus | ReviewChecklistStatus


class EvidenceReviewState(BaseModel):
    incident_id: str
    packet_filename: str
    status: ReviewStatus
    reviewer: str
    ready_to_submit: bool
    blocker_count: int
    next_action: str
    checklist: list[ReviewChecklistItem]
    timeline: list[ReviewTimelineEvent]


class ReviewDecisionRequest(BaseModel):
    reviewer: str = "Operations Manager"
    decision: ReviewStatus
    note: str
```

- [ ] **Step 4: Implement `review_trail.py`**

The service must:
- build a default demo state with two blockers: customer communication and disposal records,
- include timeline events for packet generation, automated checks, and reviewer queue,
- return approved state only through `apply_review_decision(..., decision="approved")`,
- return needs-changes state when the decision is `"needs-changes"`.

- [ ] **Step 5: Run service tests**

Run: `cd services/api && uv run pytest tests/test_review_trail.py -q`

Expected: PASS after the service is implemented and API tests are still absent.

## Task 2: Backend API Routes

**Files:**
- Modify: `services/api/src/batchhelm_api/app.py`
- Modify: `services/api/tests/test_review_trail.py`

- [ ] **Step 1: Add API tests**

```python
def test_demo_review_endpoint_returns_review_gate() -> None:
    response = make_client().get("/api/evidence/demo-review")

    assert response.status_code == 200
    payload = response.json()
    assert payload["packet_filename"].endswith(".md")
    assert payload["status"] == "needs-changes"
    assert payload["blocker_count"] == 2


def test_demo_review_decision_endpoint_returns_approved_state() -> None:
    response = make_client().post(
        "/api/evidence/demo-review/decision",
        json={
            "reviewer": "Operations Manager",
            "decision": "approved",
            "note": "Approved for supplier submission.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "approved"
    assert payload["ready_to_submit"] is True
    assert payload["timeline"][-1]["title"] == "Packet Approved"
```

- [ ] **Step 2: Run tests to verify route failure**

Run: `cd services/api && uv run pytest tests/test_review_trail.py -q`

Expected: FAIL with 404 until routes are added.

- [ ] **Step 3: Add FastAPI routes**

In `app.py`, import review models and helpers, then add:

```python
@app.get("/api/evidence/demo-review", response_model=EvidenceReviewState)
async def demo_evidence_review() -> EvidenceReviewState:
    incident, analysis, packet = _build_demo_packet_context()
    return build_demo_review_state(incident=incident, analysis=analysis, packet=packet)


@app.post("/api/evidence/demo-review/decision", response_model=EvidenceReviewState)
async def demo_evidence_review_decision(
    request: ReviewDecisionRequest,
) -> EvidenceReviewState:
    incident, analysis, packet = _build_demo_packet_context()
    return apply_review_decision(
        incident=incident,
        analysis=analysis,
        packet=packet,
        reviewer=request.reviewer,
        decision=request.decision,
        note=request.note,
    )
```

Refactor `_build_demo_evidence_packet()` to reuse `_build_demo_packet_context()`.

- [ ] **Step 4: Run backend verification**

Run: `cd services/api && uv run pytest -q`

Expected: PASS.

## Task 3: Dashboard Review Gate

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/styles.css`

- [ ] **Step 1: Add frontend types and API helpers**

Add `EvidenceReviewState`, `ReviewChecklistItem`, `ReviewTimelineEvent`, `ReviewStatus`, `fetchEvidenceReview()`, and `submitReviewDecision()`.

- [ ] **Step 2: Load review state with packet state**

In `App`, add `review`, `reviewState`, and `reviewError`. Load review state after dashboard sync and when packet preview is refreshed.

- [ ] **Step 3: Add review gate UI**

Inside `EvidenceProgress`, render:
- status chip with `Approved`, `Needs Changes`, or `Pending`,
- blocker count and next action,
- checklist rows,
- timeline rows,
- `Request changes` and `Approve packet` buttons.

- [ ] **Step 4: Apply decisions locally from API response**

Wire the action buttons to `submitReviewDecision()` with notes:
- `approved`: `"Approved for supplier submission."`
- `needs-changes`: `"Resolve open evidence blockers before submission."`

- [ ] **Step 5: Run frontend build**

Run: `cd apps/web && npm run build`

Expected: PASS.

## Task 4: Docs, Visual QA, And Push

**Files:**
- Modify: `README.md`
- Modify after capture: `docs/design-assets/screenshots/dashboard-desktop.png`
- Modify after capture: `docs/design-assets/screenshots/dashboard-mobile.png`

- [ ] **Step 1: Document endpoints**

Add:

```markdown
| `GET` | `/api/evidence/demo-review` | Returns packet review readiness, blockers, and audit timeline |
| `POST` | `/api/evidence/demo-review/decision` | Projects an approval or changes-requested review decision |
```

- [ ] **Step 2: Run verification**

Run:

```bash
cd services/api && uv run pytest -q
cd ../../apps/web && npm run build
cd ../.. && scripts/check-attribution.sh
```

- [ ] **Step 3: Capture screenshots**

Run the API and web app, capture desktop and mobile screenshots, and inspect that the review gate does not overlap the evidence packet preview.

- [ ] **Step 4: Commit and push**

```bash
git add services/api/src/batchhelm_api services/api/tests apps/web/src README.md docs/design-assets/screenshots docs/superpowers/plans/2026-06-26-batchhelm-review-trail.md
git commit -m "feat: add evidence review trail"
git push origin main
```

## Self-Review

- Spec coverage: The plan adds a backend review service, API routes, dashboard review actions, docs, tests, screenshots, and push steps.
- Placeholder scan: No step contains deferred implementation wording; all required endpoints, states, and verification commands are named.
- Type consistency: Backend and frontend both use `EvidenceReviewState`, `ReviewStatus`, checklist items, and timeline events.
