# BatchHelm Evidence Packet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an audit-ready recall evidence packet that can be previewed in the dashboard and downloaded as Markdown.

**Architecture:** Add a deterministic backend packet builder that composes the existing recall analysis and shelf inspection data into structured Markdown. Expose JSON and attachment routes, then connect the existing Evidence Packet Progress panel to preview and download the generated packet.

**Tech Stack:** FastAPI, Pydantic v2, pytest, React, TypeScript, Vite, CSS modules-by-convention.

---

## File Structure

- Create: `services/api/src/batchhelm_api/evidence_packet.py`
  - Owns packet assembly, Markdown rendering, and stable file naming.
- Modify: `services/api/src/batchhelm_api/models.py`
  - Adds `EvidencePacketSection` and `EvidencePacket`.
- Modify: `services/api/src/batchhelm_api/app.py`
  - Adds `/api/evidence/demo-packet` JSON and `/api/evidence/demo-packet.md` attachment routes.
- Create: `services/api/tests/test_evidence_packet.py`
  - Covers deterministic packet content and attachment headers.
- Modify: `apps/web/src/types.ts`
  - Adds frontend packet preview type.
- Modify: `apps/web/src/api.ts`
  - Adds `fetchEvidencePacket()` and `evidencePacketDownloadUrl`.
- Modify: `apps/web/src/App.tsx`
  - Turns the Evidence panel action into preview/download behavior.
- Modify: `apps/web/src/styles.css`
  - Adds compact packet preview styling.
- Modify: `README.md`
  - Documents the evidence packet endpoints and validation flow.

## Task 1: Backend Packet Model And Renderer

**Files:**
- Modify: `services/api/src/batchhelm_api/models.py`
- Create: `services/api/src/batchhelm_api/evidence_packet.py`
- Create: `services/api/tests/test_evidence_packet.py`

- [ ] **Step 1: Write renderer tests**

```python
from datetime import datetime, timezone

from batchhelm_api.evidence_packet import build_demo_shelf_inspection, build_evidence_packet
from batchhelm_api.sample_data import build_demo_incident
from batchhelm_api.workflow import analyze_recall_incident


def test_build_evidence_packet_contains_core_recall_sections() -> None:
    incident = build_demo_incident()
    analysis = analyze_recall_incident(incident)
    packet = build_evidence_packet(
        incident=incident,
        analysis=analysis,
        inspection=build_demo_shelf_inspection(),
        generated_at=datetime(2026, 6, 26, 10, 30, tzinfo=timezone.utc),
    )

    assert packet.filename == "batchhelm-recall-spinach-2026-06-evidence.md"
    assert packet.incident_id == "recall-spinach-2026-06"
    assert packet.generated_at == "2026-06-26T10:30:00+00:00"
    assert "## Executive Summary" in packet.markdown
    assert "Spinach 10 oz" in packet.markdown
    assert "L2418-L2422" in packet.markdown
    assert "| Store | SKU | Product | Lot | Quarantined | Location | Confidence |" in packet.markdown
    assert "Customer Notice Draft" in packet.markdown
    assert "Shelf Inspection Evidence" in packet.markdown
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/api && uv run pytest tests/test_evidence_packet.py -q`

Expected: FAIL because `batchhelm_api.evidence_packet` does not exist.

- [ ] **Step 3: Add Pydantic packet models**

```python
class EvidencePacketSection(BaseModel):
    title: str
    body: str


class EvidencePacket(BaseModel):
    incident_id: str
    filename: str
    generated_at: str
    sections: list[EvidencePacketSection]
    markdown: str
```

- [ ] **Step 4: Implement packet renderer**

```python
from datetime import datetime, timezone
from batchhelm_api.models import EvidencePacket, EvidencePacketSection


def build_evidence_packet(..., generated_at: datetime | None = None) -> EvidencePacket:
    timestamp = generated_at or datetime.now(timezone.utc)
    sections = [...]
    markdown = "\n\n".join(["# BatchHelm Recall Evidence Packet", *rendered_sections])
    return EvidencePacket(...)
```

The renderer must include executive summary, affected inventory, workflow timeline, staff tasks, evidence checklist, customer notice draft, memory insights, shelf inspection evidence, and review notes.

- [ ] **Step 5: Run renderer tests**

Run: `cd services/api && uv run pytest tests/test_evidence_packet.py -q`

Expected: PASS.

## Task 2: Backend API Routes

**Files:**
- Modify: `services/api/src/batchhelm_api/app.py`
- Modify: `services/api/tests/test_evidence_packet.py`

- [ ] **Step 1: Add API tests**

```python
def test_demo_evidence_packet_endpoint_returns_preview() -> None:
    response = make_client().get("/api/evidence/demo-packet")

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"].endswith(".md")
    assert payload["sections"][0]["title"] == "Executive Summary"
    assert "Regulatory Filing Package" in payload["markdown"]


def test_demo_evidence_packet_download_has_attachment_header() -> None:
    response = make_client().get("/api/evidence/demo-packet.md")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "attachment" in response.headers["content-disposition"]
    assert "batchhelm-recall-spinach-2026-06-evidence.md" in response.headers["content-disposition"]
    assert "# BatchHelm Recall Evidence Packet" in response.text
```

- [ ] **Step 2: Run API tests to verify failure**

Run: `cd services/api && uv run pytest tests/test_evidence_packet.py -q`

Expected: FAIL with 404 for packet endpoints.

- [ ] **Step 3: Add routes**

```python
from fastapi.responses import PlainTextResponse
from batchhelm_api.evidence_packet import build_demo_shelf_inspection, build_evidence_packet


@app.get("/api/evidence/demo-packet", response_model=EvidencePacket)
async def demo_evidence_packet() -> EvidencePacket:
    incident = build_demo_incident()
    return build_evidence_packet(
        incident=incident,
        analysis=analyze_recall_incident(incident),
        inspection=build_demo_shelf_inspection(),
    )


@app.get("/api/evidence/demo-packet.md", response_class=PlainTextResponse)
async def download_demo_evidence_packet() -> PlainTextResponse:
    packet = ...
    return PlainTextResponse(
        packet.markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{packet.filename}"'},
    )
```

- [ ] **Step 4: Run backend verification**

Run: `cd services/api && uv run pytest -q`

Expected: PASS.

## Task 3: Frontend Preview And Download

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/styles.css`

- [ ] **Step 1: Add frontend packet type and API helper**

```ts
export interface EvidencePacket {
  incident_id: string;
  filename: string;
  generated_at: string;
  sections: { title: string; body: string }[];
  markdown: string;
}

export const evidencePacketDownloadUrl = `${API_BASE_URL}/api/evidence/demo-packet.md`;

export async function fetchEvidencePacket(): Promise<EvidencePacket> {
  const response = await fetch(`${API_BASE_URL}/api/evidence/demo-packet`);
  if (!response.ok) {
    throw new Error(`Evidence packet request failed with ${response.status}`);
  }
  return (await response.json()) as EvidencePacket;
}
```

- [ ] **Step 2: Wire state into the dashboard**

Add `packet`, `packetState`, and `packetError` state in `App`. Pass them to `EvidenceProgress`, and add `loadEvidencePacket()` that calls `fetchEvidencePacket()`.

- [ ] **Step 3: Replace static View action**

The Evidence panel must show:
- a `Preview packet` button with a loading state,
- a `Download .md` link using `evidencePacketDownloadUrl`,
- a compact preview area with filename, generated timestamp, and the first sections.

- [ ] **Step 4: Add responsive styles**

Style `.packet-actions`, `.packet-preview`, `.packet-section`, and `.packet-error` so the panel remains compact on desktop and becomes single-column below 960px.

- [ ] **Step 5: Run frontend build**

Run: `cd apps/web && npm run build`

Expected: PASS.

## Task 4: Documentation And Submission Polish

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document endpoints**

Add these endpoint rows:

```markdown
| `GET` | `/api/evidence/demo-packet` | Returns a structured Markdown evidence packet preview |
| `GET` | `/api/evidence/demo-packet.md` | Downloads the same packet as an audit-ready Markdown attachment |
```

- [ ] **Step 2: Document validation**

Add the full verification sequence:

```bash
cd services/api && uv run pytest -q
cd ../../apps/web && npm run build
cd ../.. && scripts/check-attribution.sh
```

- [ ] **Step 3: Run documentation scan**

Run: `scripts/check-attribution.sh`

Expected: `Attribution-language scan passed.`

## Task 5: Final Verification And Commit

**Files:**
- All changed files.

- [ ] **Step 1: Run backend tests**

Run: `cd services/api && uv run pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Run frontend build**

Run: `cd apps/web && npm run build`

Expected: TypeScript and Vite build succeeds.

- [ ] **Step 3: Run attribution scan**

Run: `scripts/check-attribution.sh`

Expected: scan passes.

- [ ] **Step 4: Capture visual proof if UI changed materially**

Run the API and web app locally, then capture desktop and mobile screenshots with Playwright CLI. Confirm the packet controls do not overlap existing evidence, inspection, or milestone panels.

- [ ] **Step 5: Commit and push**

```bash
git add services/api/src/batchhelm_api services/api/tests apps/web/src README.md docs/superpowers/plans/2026-06-26-batchhelm-evidence-packet.md
git commit -m "feat: add evidence packet workflow"
git push origin main
```

## Self-Review

- Spec coverage: The plan adds backend packet generation, API delivery, dashboard preview/download, docs, tests, and final scan.
- Placeholder scan: No task depends on undefined future work; implementation snippets define the concrete interfaces and routes.
- Type consistency: Backend uses `EvidencePacket`/`EvidencePacketSection`; frontend mirrors those fields with snake-case keys from the API.
