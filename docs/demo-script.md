# BatchHelm Demo Script (under 3 minutes)

Target: Qwen Global AI Hackathon. Primary track: **Autopilot Agent**. Secondary
track: **Agent Society**.

## Setup Before Recording

1. Set `QWEN_API_KEY` and start the API and web application.
2. Verify `/api/v1/qwen/status` reports `mode: "live"` and `/api/v1/qwen/proof`
   contains a recent successful receipt.
3. Open the dashboard Qwen Cloud evidence control and confirm it displays
   `Verified`, the current model, request ID, latency, and UTC timestamp.
4. Open the dashboard at 1280 x 720 with browser zoom at 100%.
5. Keep `sample-data` open in the file chooser.
6. Use `inventory-spinach-invalid.csv` so the review warnings are visible.

Deterministic fallback is for tests and local recovery checks. The submission
recording must visibly show live Qwen source badges and model status.

## Run Of Show

| Time | On screen | Say |
| --- | --- | --- |
| 0:00-0:14 | Dashboard, then **New recall** | "A supplier recall arrives, but a small grocery team still has to find the right lots, shelves, people, and evidence. BatchHelm turns that packet into a controlled response." |
| 0:14-0:34 | Files stage | "I add the supplier PDF, an inventory export, and a real cooler photo. The API streams them into immutable artifact storage and starts one idempotent intake." |
| 0:34-0:48 | Extraction progress to Review | "Qwen reads text or rendered notice pages while deterministic parsers validate inventory. This is an operational workflow, not a chat response." |
| 0:48-1:08 | Criteria fields and provenance | "Every safety-critical field shows confidence and its source location. This supplier field is low confidence, so I correct it before anything can run." |
| 1:08-1:23 | Save correction; inventory warnings | "The override becomes versioned reviewer evidence. Six valid rows total 23 units, while a negative quantity and duplicate identity are isolated as warnings." |
| 1:23-1:37 | Launch summary; confirm and run | "Confirmation freezes one immutable incident snapshot. A new request ID can now launch exactly one durable run." |
| 1:37-2:00 | Agent Mission Control waves | "Nine specialists execute as a dependency graph. Inventory matching and shelf vision run in parallel, then risk, tasks, communications, memory, and compliance follow." |
| 2:00-2:17 | Shelf Vision inspector | "The vision agent is reading the uploaded Store B photo, not a demo placeholder. Live Qwen evidence is labeled; if vision is unavailable, BatchHelm infers no positive match and requires review." |
| 2:17-2:31 | Refresh and reconnect | "After refresh, the same intake, run ID, and ordered event history return. Events are persisted before publication, and completed waves are restart checkpoints." |
| 2:31-2:47 | Review gate and audit timeline | "Actions and customer communication are assembled, but critical release still requires a durable human decision with an immutable audit history." |
| 2:47-2:58 | Evidence packet, management briefing, public URL | "BatchHelm closes the loop with an audit-ready evidence packet and management briefing, deployed on Alibaba Cloud with Qwen as the reasoning engine." |

## Recording Checks

- Keep the final cut under 3:00.
- Show `mode: live` and at least one `qwen` source badge.
- Open the top-bar Qwen Cloud evidence control and show the redacted receipt.
- Keep the low-confidence field, provenance locator, two inventory warnings,
  shelf filename, run ID, and review decision legible.
- Show the public Alibaba Cloud URL in the final frame.
- Do not imply that fallback screenshots prove live Qwen execution.

## Key Lines

- "Qwen handles uncertainty; typed contracts and human review control action."
- "One packet becomes one immutable incident and one recoverable agent run."
- "The uploaded shelf evidence follows the incident through restart and audit."
