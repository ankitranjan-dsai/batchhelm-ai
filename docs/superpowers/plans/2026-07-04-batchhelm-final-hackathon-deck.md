# BatchHelm Final Hackathon Deck Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the sparse 11-slide source deck with the approved ten-slide, proof-first BatchHelm hackathon presentation using real product evidence, editable PowerPoint objects, verified benchmark claims, and Ankit Ranjan-only authorship.

**Architecture:** Use the existing PowerPoint as the template source, create a validated ten-slide starter deck from an explicit source-to-output frame map, and edit that starter with `@oai/artifact-tool`. Real screenshots and rendered repository evidence provide product proof; native PowerPoint shapes, connectors, and charts provide only the system diagrams and quantitative comparisons. Keep scripts and renders in an external scratch directory, export only the reviewed PPTX into the repository, and gate each narrative milestone with full-slide rendering before committing.

**Tech Stack:** JavaScript ES modules, `@oai/artifact-tool`, Microsoft PowerPoint-compatible PPTX, presentation template-following scripts, `pdftoppm`, LibreOffice headless rendering, PowerPoint AppleScript document properties, repository attribution checks, GitHub Actions.

---

## Fixed Inputs And Paths

Use these exact paths throughout implementation:

```bash
REPO="/Users/ankit/Documents/New project/batchhelm-ai"
DECK="$REPO/docs/presentation/batchhelm-ai-hackathon-deck.pptx"
SCRATCH="/var/folders/z8/53shggmj1356m_q3ggt1_wq40000gn/T/codex-presentations/019f0283-abda-7c00-ba79-fa5d74bc9345/batchhelm-final-deck"
TMP="$SCRATCH/tmp"
PRESENTATION_SKILL="/Users/ankit/.codex/plugins/cache/openai-primary-runtime/presentations/26.630.12135/skills/presentations"
NODE="/Users/ankit/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
PYTHON="/Users/ankit/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
export PATH="/Users/ankit/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin:$PATH"
export NODE_PATH="/Users/ankit/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"
```

The source-to-output slide map is fixed:

| Output | Source | Reason |
|---|---:|---|
| 1 | 1 | Cover composition |
| 2 | 2 | Problem framing |
| 3 | 3 | Workflow proof |
| 4 | 4 | Evidence gate |
| 5 | 6 | Model responsibilities |
| 6 | 5 | Agent Society |
| 7 | 7 | Persistence architecture |
| 8 | 8 | Benchmark |
| 9 | 9 | Sample incident |
| 10 | 11 | Close |

Source slide 10 is omitted because its limitations copy is stale and the approved close already states unverified capabilities honestly.

## Task 1: Establish A Reproducible Template Baseline

**Files:**
- Read: `docs/presentation/batchhelm-ai-hackathon-deck.pptx`
- Create outside repository: `$SCRATCH/source-deck.pptx`
- Create outside repository: `$TMP/template-inspect/`
- Create outside repository: `$TMP/template-audit.txt`
- Create outside repository: `$TMP/deviation-log.txt`
- Create outside repository: `$TMP/source-core.xml`

- [x] **Step 1: Confirm the repository is clean and preserve the approved source**

Run:

```bash
cd "$REPO"
git status --short --branch
mkdir -p "$TMP"
cp "$DECK" "$SCRATCH/source-deck.pptx"
shasum -a 256 "$DECK" "$SCRATCH/source-deck.pptx"
```

Expected: `main` tracks `origin/main`, no uncommitted repository files, and both SHA-256 values match.

- [x] **Step 2: Inspect every inherited slide and object**

Run:

```bash
"$NODE" "$PRESENTATION_SKILL/template_following_scripts/inspect_template_deck.mjs" \
  --workspace "$TMP" \
  --pptx "$SCRATCH/source-deck.pptx" \
  --out-dir template-inspect
```

Expected: eleven slide PNGs, eleven layout JSON files, `template-inspect.ndjson`, and `template-manifest.json` are created. Build the audit montage with:

```bash
"$PYTHON" "$PRESENTATION_SKILL/template_following_scripts/make_contact_sheet.py" \
  "$TMP/template-inspect/source-slides/"*.png \
  --output "$TMP/template-inspect/source-montage.png"
```

- [x] **Step 3: Record the template audit and intentional deviations**

Create `$TMP/template-audit.txt` with:

```text
Source: docs/presentation/batchhelm-ai-hackathon-deck.pptx
Canvas: 1280 x 720, 16:9
Structure: 11 sparse text-led slides; every slide has one inherited title and one inherited body textbox.
Reusable patterns: source slide 1 for cover; source slides 2-9 for evidence and technical content; source slide 11 for close.
Typography: inherited Calibri hierarchy may be intentionally restyled to the approved Aptos/Aptos Display system.
Spacing: retain the source title/body structure, reposition both inherited textboxes, and add evidence only inside declared frame-map zones.
Placeholders: both inherited textboxes must be rewritten or deleted; no empty structural placeholder may survive.
Assets: only committed BatchHelm screenshots, sample packet evidence, benchmark data, and native editable diagrams/charts.
Insertion contract: no fresh slides, fake UI, stock image, generated approximation, or unbounded overlay.
```

Create `$TMP/deviation-log.txt` with:

```text
Slides 1-10: Restyle inherited title/body typography and placement to the approved proof-first visual system.
Slides 1-4: Add authentic intake and evidence imagery inside declared zones.
Slide 5: Add Qwen responsibility/control comparison inside the declared zone.
Slides 6-7: Add editable native architecture diagrams inside declared zones.
Slide 8: Add an editable native benchmark chart inside the declared zone.
Slide 9: Add authentic incident evidence and metrics inside the declared zone.
Slide 10: Add repository, CI, license, and Alibaba deployment-architecture proof inside the declared zone.
Source slide 10: Omitted because its stale limitations copy is superseded by the approved close.
```

- [x] **Step 4: Record source metadata before editing**

Run:

```bash
unzip -p "$SCRATCH/source-deck.pptx" docProps/core.xml > "$TMP/source-core.xml"
rg -n "creator|lastModifiedBy|title|description" "$TMP/source-core.xml"
```

Expected: the inherited file's legacy metadata is visible, including the values that must not survive the final export.

- [x] **Step 5: Verify the source audit**

Open the montage and all eleven full-size slide renders. Confirm the canvas is 16:9, title/body placeholders are readable, and no visual element outside the inherited title/body fields must be preserved.

## Task 2: Prepare Authentic Evidence Assets

**Files:**
- Read: `docs/design-assets/screenshots/intake-files-desktop.png`
- Read: `docs/design-assets/screenshots/intake-review-desktop.png`
- Read: `docs/design-assets/screenshots/intake-review-mobile.png`
- Read: `docs/design-assets/screenshots/mission-control-desktop.png`
- Read: `sample-data/recall-notice-spinach.pdf`
- Read: `sample-data/store-b-cooler-spinach.png`
- Read: `docs/benchmarks/agent-society-vs-single-agent.md`
- Create outside repository: `$TMP/assets/`
- Create outside repository: `$TMP/evidence-manifest.json`

- [x] **Step 1: Copy approved raster evidence into scratch**

Run:

```bash
mkdir -p "$TMP/assets"
cp "$REPO/docs/design-assets/screenshots/intake-files-desktop.png" "$TMP/assets/"
cp "$REPO/docs/design-assets/screenshots/intake-review-desktop.png" "$TMP/assets/"
cp "$REPO/docs/design-assets/screenshots/intake-review-mobile.png" "$TMP/assets/"
cp "$REPO/docs/design-assets/screenshots/mission-control-desktop.png" "$TMP/assets/"
cp "$REPO/sample-data/store-b-cooler-spinach.png" "$TMP/assets/"
```

Expected: five repository-authentic PNG assets exist in scratch.

- [x] **Step 2: Render the supplier notice without modifying the source PDF**

Run:

```bash
pdftoppm \
  -png \
  -f 1 \
  -singlefile \
  -r 180 \
  "$REPO/sample-data/recall-notice-spinach.pdf" \
  "$TMP/assets/recall-notice-spinach"
```

Expected: `$TMP/assets/recall-notice-spinach.png` is a sharp first-page render.

- [x] **Step 3: Create a claim-and-asset manifest**

Create `$TMP/evidence-manifest.json` with this exact data contract:

```json
{
  "owner": "Ankit Ranjan",
  "incidentLabel": "Synthetic demo packet",
  "workflow": {
    "acceptedRows": 6,
    "rejectedRows": 2,
    "onHandUnits": 23,
    "stores": 2,
    "warnings": 2,
    "affectedLots": 5,
    "orderedEvents": 37
  },
  "benchmark": {
    "dagMeanMs": 1095.3,
    "sequentialMeanMs": 1633.9,
    "speedup": 1.49,
    "syntheticAgentDelayMs": 180,
    "visionFailureDagCompleted": "4/9",
    "visionFailureSequentialCompleted": "3/9",
    "crashRerunDag": "3/9",
    "crashRerunSequential": "9/9"
  },
  "claimsNotYetAllowed": [
    "public application URL",
    "live Qwen execution proof",
    "live Qwen latency",
    "customer deployment"
  ]
}
```

- [x] **Step 4: Cross-check benchmark values**

Run:

```bash
rg -n "1095\\.3|1633\\.9|1\\.49|180|4/9|3/9|9/9" \
  "$REPO/docs/benchmarks/agent-society-vs-single-agent.md"
```

Expected: every numeric claim in the manifest is supported by the benchmark document.

## Task 3: Build And Validate The Ten-Slide Starter

**Files:**
- Create outside repository: `$TMP/template-frame-map.json`
- Create outside repository: `$TMP/template-starter.pptx`
- Create outside repository: `$TMP/template-starter-preview/`
- Create outside repository: `$TMP/template-starter-layout/`
- Create outside repository: `$TMP/template-starter-contact-sheet.png`

- [x] **Step 1: Write the complete frame map**

Create `$TMP/template-frame-map.json` with root keys `outputSlides` and `omittedSourceSlides`. Every output slide must target both inherited textbox IDs from `template-inspect.ndjson`; every new visual zone must be declared. Use this pattern for each slide:

```json
{
  "outputSlides": [
    {
      "outputSlide": 1,
      "sourceSlide": 1,
      "narrativeRole": "product-first opening proof",
      "reuseMode": "duplicate-slide",
      "editTargets": [
        {
          "sourceElementId": "sh/cvixczed",
          "action": "rewrite-and-reposition",
          "intent": "Use as the BatchHelm title and product promise."
        },
        {
          "sourceElementId": "sh/5gbq1ory",
          "action": "rewrite-and-reposition",
          "intent": "Use as the event and author line."
        },
        {
          "action": "add",
          "newPrimitiveAllowed": true,
          "mustNotOverlapInherited": true,
          "reason": "Add authentic Review workspace evidence as the primary visual.",
          "zone": { "left": 486, "top": 74, "width": 742, "height": 572 }
        }
      ]
    }
  ],
  "omittedSourceSlides": [
    {
      "sourceSlide": 10,
      "reason": "Stale limitations copy is superseded by the approved evidence-led close."
    }
  ]
}
```

Use these inherited source IDs:

| Output | Source | Title ID | Body ID |
|---|---:|---|---|
| 1 | 1 | `sh/cvixczed` | `sh/5gbq1ory` |
| 2 | 2 | `sh/5o7qpg3e` | `sh/g3ex0nux` |
| 3 | 3 | `sh/o7qpg3ex` | `sh/dsji5sne` |
| 4 | 4 | `sh/qtcj6tov` | `sh/je9cvixc` |
| 5 | 6 | `sh/ylc7u54z` | `sh/r65wjudg` |
| 6 | 5 | `sh/ovahoza1` | `sh/dg7adsji` |
| 7 | 7 | `sh/x4nap4r6` | `sh/8jqh0fep` |
| 8 | 8 | `sh/u9knih4b` | `sh/judg7ads` |
| 9 | 9 | `sh/ovahoza1` | `sh/dg7adsji` |
| 10 | 11 | `sh/6tovahoz` | `sh/vahoza1g` |

Use these approved add zones in source pixel coordinates:

| Slide | Zone |
|---|---|
| 1 | `{ "left": 486, "top": 74, "width": 742, "height": 572 }` |
| 2 | `{ "left": 610, "top": 154, "width": 602, "height": 510 }` |
| 3 | `{ "left": 420, "top": 154, "width": 792, "height": 510 }` |
| 4 | `{ "left": 610, "top": 154, "width": 602, "height": 510 }` |
| 5 | `{ "left": 646, "top": 154, "width": 566, "height": 510 }` |
| 6 | `{ "left": 438, "top": 154, "width": 774, "height": 510 }` |
| 7 | `{ "left": 438, "top": 154, "width": 774, "height": 510 }` |
| 8 | `{ "left": 438, "top": 154, "width": 774, "height": 510 }` |
| 9 | `{ "left": 514, "top": 154, "width": 698, "height": 510 }` |
| 10 | `{ "left": 596, "top": 154, "width": 616, "height": 510 }` |

- [x] **Step 2: Validate the frame map before touching the deck**

Run:

```bash
"$NODE" "$PRESENTATION_SKILL/template_following_scripts/validate_template_plan.mjs" \
  --workspace "$TMP" \
  --map "$TMP/template-frame-map.json" \
  --inspect "$TMP/template-inspect/template-inspect.ndjson" \
  --source-slide-count 11
```

Expected: all ten output slides pass; no add-only slide, undeclared primitive, or missing inherited target is reported.

- [x] **Step 3: Generate the starter deck**

Run:

```bash
"$NODE" "$PRESENTATION_SKILL/template_following_scripts/prepare_template_starter_deck.mjs" \
  --workspace "$TMP" \
  --pptx "$SCRATCH/source-deck.pptx" \
  --map "$TMP/template-frame-map.json" \
  --out "$TMP/template-starter.pptx" \
  --preview-dir "$TMP/template-starter-preview" \
  --layout-dir "$TMP/template-starter-layout" \
  --contact-sheet "$TMP/template-starter-contact-sheet.png"
```

Expected: a ten-slide PPTX with source slide 10 omitted and the approved order applied.

- [x] **Step 4: Inspect the starter and confirm inherited object order**

Review `$TMP/template-starter-contact-sheet.png` and all JSON files in `$TMP/template-starter-layout`. Confirm that each slide contains exactly the two inherited textboxes before any approved new primitive is added.

```bash
find "$TMP/template-starter-layout" -name '*.json' -print | sort
```

Expected: ten layout files exist, each inherited title is the first shape, each inherited body is the second shape, and the contact sheet confirms the source layout was retained.

## Task 4: Implement The Deck Builder Foundation

**Files:**
- Create outside repository: `$SCRATCH/build-final-deck.mjs`
- Create outside repository: `$SCRATCH/set-deck-metadata.applescript`
- Modify: `docs/presentation/batchhelm-ai-hackathon-deck.pptx`

- [x] **Step 1: Create the artifact-tool builder**

Start `$SCRATCH/build-final-deck.mjs` with:

```javascript
import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const scratch = process.env.SCRATCH;
const repo = process.env.REPO;
const starter = path.join(scratch, "tmp", "template-starter.pptx");
const output = path.join(
  repo,
  "docs",
  "presentation",
  "batchhelm-ai-hackathon-deck.pptx",
);
const palette = {
  commandTeal: "#0B3D38",
  activeTeal: "#087C72",
  evidenceWhite: "#F8FBFA",
  darkText: "#132925",
  mutedText: "#5B6F6A",
  recallRed: "#B42318",
  reviewAmber: "#C47A00",
  border: "#D6E3DF",
};
const evidence = JSON.parse(
  await fs.readFile(path.join(scratch, "tmp", "evidence-manifest.json"), "utf8"),
);

const presentation = await PresentationFile.importPptx(
  await FileBlob.load(starter),
);

function slideAt(oneBasedIndex) {
  return presentation.slides.items[oneBasedIndex - 1];
}

function inheritedShapes(slide) {
  const shapes = slide.shapes.items;
  if (!Array.isArray(shapes) || shapes.length < 2) {
    throw new Error("Mapped source slide is missing inherited title/body shapes.");
  }
  return { title: shapes[0], body: shapes[1] };
}

function writeTitle(slide, text) {
  const { title: shape } = inheritedShapes(slide);
  shape.text = text;
  shape.text.style = {
    fontSize: 35,
    fontFamily: "Aptos Display",
    bold: true,
    color: palette.darkText,
  };
}

function writeBody(slide, text) {
  const { body: shape } = inheritedShapes(slide);
  shape.text = text;
  shape.text.style = {
    fontSize: 17,
    fontFamily: "Aptos",
    color: palette.darkText,
  };
}
```

During implementation, inspect the imported starter once with `presentation.inspect(...)`. If inherited object order differs from title-then-body on any slide, resolve those two objects by the IDs in `$TMP/starter-targets.json` instead of positional indexing.

- [x] **Step 2: Add reusable composition helpers**

Implement helpers for:

```javascript
function addLabel(slide, text, position, style = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position,
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    fontFamily: "Aptos",
    fontSize: 16,
    color: palette.darkText,
    ...style,
  };
  return shape;
}

function addMetric(slide, value, label, position, accent) {
  const node = slide.shapes.add({
    geometry: "roundRect",
    position,
    fill: palette.evidenceWhite,
    line: { style: "solid", fill: accent, width: 2 },
    borderRadius: "rounded-md",
  });
  node.text = `${value}\n${label}`;
  node.text.style = {
    fontFamily: "Aptos",
    fontSize: 16,
    bold: true,
    color: palette.darkText,
    alignment: "center",
  };
  return node;
}

async function addImageCrop(slide, imagePath, position, alt) {
  const bytes = await fs.readFile(imagePath);
  return slide.images.add({
    blob: bytes.buffer.slice(
      bytes.byteOffset,
      bytes.byteOffset + bytes.byteLength,
    ),
    contentType: "image/png",
    alt,
    fit: "cover",
    position,
    geometry: "roundRect",
    borderRadius: "rounded-md",
  });
}

function addNode(slide, title, subtitle, position, accent) {
  const node = slide.shapes.add({
    geometry: "roundRect",
    position,
    fill: palette.evidenceWhite,
    line: { style: "solid", fill: accent, width: 1 },
    borderRadius: "rounded-md",
  });
  node.text = subtitle ? `${title}\n${subtitle}` : title;
  node.text.style = {
    fontFamily: "Aptos",
    fontSize: 16,
    bold: true,
    color: palette.darkText,
    alignment: "center",
  };
  return node;
}

function addConnector(slide, from, to) {
  return slide.shapes.connect(from, to, {
    kind: "elbow",
    fromSide: "right",
    toSide: "left",
    line: { style: "solid", fill: palette.border, width: 2 },
    head: { type: "arrow", width: "sm", length: "sm" },
  });
}
```

Rules enforced by the helpers:

- all content uses the approved palette;
- titles are at least 35 pt and remain one line;
- body text is at least 16 pt;
- corners are at most 8 px;
- images use the real files in `$TMP/assets`;
- connectors remain behind node labels using the connector API's default z-order;
- no gradient, decorative orb, fake browser frame, or stock image is created.

- [x] **Step 3: Add deterministic export and render hooks**

End the script with:

```javascript
for (let i = 1; i <= 10; i += 1) {
  assertOneLineTitle(slideAt(i));
}

const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(output);
console.log(`Exported ${output}`);
```

Run:

```bash
cd "$SCRATCH"
REPO="$REPO" SCRATCH="$SCRATCH" "$NODE" build-final-deck.mjs
```

Expected: the deck exports successfully and still has ten slides.

## Task 5: Build Slides 1-4 — Product Proof And Safety

**Files:**
- Modify outside repository: `$SCRATCH/build-final-deck.mjs`
- Modify: `docs/presentation/batchhelm-ai-hackathon-deck.pptx`
- Create outside repository: `$TMP/checkpoint-1/`

- [x] **Step 1: Compose the product-first cover**

Implement slide 1 with:

- `BatchHelm` as the headline;
- `A recall packet becomes a controlled response.` as the product promise;
- `Real intake. Nine specialist agents. Human evidence gate.`;
- `Qwen Global AI Hackathon · Ankit Ranjan`;
- a sharp crop of `intake-review-desktop.png`.

Do not add a deployment badge, live-Qwen badge, feature list, or agenda.

- [x] **Step 2: Compose the concrete recall problem**

Implement slide 2 with the five approved questions, the rendered supplier notice, and `store-b-cooler-spinach.png`. Label the packet `Synthetic demo packet`; use recall red only as a state signal.

- [x] **Step 3: Compose Files → Review → Launch**

Implement slide 3 with readable crops of the Files and Review screens, the three-stage workflow label, and these exact metrics:

```text
6 accepted · 2 rejected · 23 units · 2 stores · 2 warnings
```

Include a field-level provenance and confidence callout.

- [x] **Step 4: Compose the human evidence gate**

Implement slide 4 with versioned correction, stale conflict, immutable confirm, launch block, and neutral shelf fallback. Use a distinct crop of the Review screen and the mobile screenshot only where it proves warning/review behavior.

- [x] **Step 5: Render and inspect slides 1-4**

Run:

```bash
rm -rf "$TMP/checkpoint-1"
mkdir -p "$TMP/checkpoint-1"
"$PYTHON" "$PRESENTATION_SKILL/container_tools/render_slides.py" \
  "$DECK" \
  --output_dir "$TMP/checkpoint-1"
```

Inspect every full-size slide. Expected: no title wrap, screenshot blur, screenshot reuse with the same crop, hidden provenance, or overlapping text.

- [x] **Step 6: Commit and push the first narrative checkpoint**

Run:

```bash
cd "$REPO"
git diff --check
./scripts/check-attribution.sh
git add docs/presentation/batchhelm-ai-hackathon-deck.pptx
git commit --author="Ankit Ranjan <ankit0ranjan@gmail.com>" \
  -m "feat(presentation): lead with real intake evidence"
git push origin main
```

Expected: one meaningful binary deck commit authored by Ankit Ranjan is visible on `main`.

## Task 6: Build Slides 5-7 — Qwen, Agents, And Durability

**Files:**
- Modify outside repository: `$SCRATCH/build-final-deck.mjs`
- Modify: `docs/presentation/batchhelm-ai-hackathon-deck.pptx`
- Create outside repository: `$TMP/checkpoint-2/`

- [x] **Step 1: Explain Qwen's specific responsibilities**

Implement slide 5 with six responsibilities:

```text
Recall extraction · Shelf interpretation · Inventory reasoning
Risk classification · Customer communication · Management briefing
```

Place the engineering controls beside them:

```text
Structured JSON · Pydantic validation · Provider source
Bounded retries · Literal fallback · Reviewer escalation
```

Do not imply that a live provider run or provider latency has been captured.

- [x] **Step 2: Draw the six-wave Agent Society**

On slide 6, create all connectors before nodes. Represent:

1. Recall Intake;
2. Document Extraction;
3. Inventory Matching and Shelf Vision;
4. Risk Scoring and Memory;
5. Operations Task and Communications;
6. Compliance Evidence.

Show nine specialists across the six waves and use `mission-control-desktop.png` as supporting evidence, not as an unreadable full-screen thumbnail.

- [x] **Step 3: Draw the persistence architecture**

Implement slide 7 with four visibly separate responsibilities:

- intake lifecycle and confirmed snapshots;
- immutable artifact files;
- orchestration runs, events, and checkpoints;
- memory and human review ledgers.

Add concise labels for request UUID idempotency, persist-before-publish SSE, replay, typed checkpoints, and startup recovery. State `Current SQLite lifecycle: one API replica` exactly once.

- [x] **Step 4: Render and inspect slides 5-7**

Run:

```bash
rm -rf "$TMP/checkpoint-2"
mkdir -p "$TMP/checkpoint-2"
"$PYTHON" "$PRESENTATION_SKILL/container_tools/render_slides.py" \
  "$DECK" \
  --output_dir "$TMP/checkpoint-2"
```

Expected: Qwen has concrete work, all nine agents and six waves are legible, connectors sit behind nodes, and persistence stores are not visually merged.

- [x] **Step 5: Commit and push the technical-depth checkpoint**

Run:

```bash
cd "$REPO"
git diff --check
./scripts/check-attribution.sh
git add docs/presentation/batchhelm-ai-hackathon-deck.pptx
git commit --author="Ankit Ranjan <ankit0ranjan@gmail.com>" \
  -m "feat(presentation): show agent and durability architecture"
git push origin main
```

Expected: the second deck checkpoint is visible on `main`.

## Task 7: Build Slides 8-10 — Benchmark, Incident, And Close

**Files:**
- Modify outside repository: `$SCRATCH/build-final-deck.mjs`
- Modify: `docs/presentation/batchhelm-ai-hackathon-deck.pptx`
- Create outside repository: `$TMP/checkpoint-3/`

- [x] **Step 1: Build the benchmark comparison**

Implement slide 8 with an editable native horizontal bar comparison:

```javascript
const latencyRows = [
  { label: "Agent Society DAG", value: evidence.benchmark.dagMeanMs },
  { label: "Sequential baseline", value: evidence.benchmark.sequentialMeanMs },
];
```

Show `1.49x faster`, both resilience comparisons, and this disclosure in at least 16 pt:

```text
Deterministic fallback benchmark; identical synthetic 180 ms delay per agent isolates orchestration strategy from provider latency.
```

- [x] **Step 2: Return to the sample incident**

Implement slide 9 with a fresh, readable Review crop, the cooler photo, and an evidence trail:

```text
Notice → Confirmed snapshot → Durable run → 37 ordered events
```

Show `2 stores`, `23 units`, `6 valid rows`, `2 safely rejected`, `5 lots`, and `1 optional shelf artifact`. Label the packet `Synthetic demo incident`.

- [x] **Step 3: Build the honest close**

Implement slide 10 with:

- `github.com/ankitranjan-dsai/batchhelm-ai`;
- MIT license;
- green checks for backend, frontend, attribution, and Docker;
- the implemented Alibaba Cloud deployment architecture;
- `Ankit Ranjan`.

Do not show a public application URL or live-Qwen proof until those artifacts exist.

- [x] **Step 4: Render and inspect slides 8-10**

Run:

```bash
rm -rf "$TMP/checkpoint-3"
mkdir -p "$TMP/checkpoint-3"
"$PYTHON" "$PRESENTATION_SKILL/container_tools/render_slides.py" \
  "$DECK" \
  --output_dir "$TMP/checkpoint-3"
```

Expected: chart numbers match the source, synthetic delay is clearly disclosed, the sample incident is not framed as a customer, and the close contains no unsupported badge.

- [x] **Step 5: Commit and push the complete narrative**

Run:

```bash
cd "$REPO"
git diff --check
./scripts/check-attribution.sh
git add docs/presentation/batchhelm-ai-hackathon-deck.pptx
git commit --author="Ankit Ranjan <ankit0ranjan@gmail.com>" \
  -m "feat(presentation): complete benchmark and submission close"
git push origin main
```

Expected: the full ten-slide narrative is visible on `main`.

## Task 8: Sanitize And Verify PowerPoint Authorship

**Files:**
- Modify outside repository: `$SCRATCH/set-deck-metadata.applescript`
- Modify: `docs/presentation/batchhelm-ai-hackathon-deck.pptx`
- Create outside repository: `$TMP/final-core.xml`

- [x] **Step 1: Check whether artifact export already replaced legacy metadata**

Run:

```bash
unzip -p "$DECK" docProps/core.xml > "$TMP/final-core.xml"
rg -n "creator|lastModifiedBy|title|subject|description|python-pptx|Steve Canny" \
  "$TMP/final-core.xml"
```

Acceptance:

- creator and last modifier are `Ankit Ranjan`;
- title is `BatchHelm AI - Qwen Global AI Hackathon`;
- subject is `Production-shaped recall autopilot`;
- no `python-pptx`, `Steve Canny`, or third-party author-credit wording remains.

- [x] **Step 2: Use PowerPoint document properties if metadata is not clean**

Create `$SCRATCH/set-deck-metadata.applescript`:

```applescript
on run argv
  set deckPath to item 1 of argv
  tell application "Microsoft PowerPoint"
    open POSIX file deckPath
    tell active presentation
      set value of document property "Author" to "Ankit Ranjan"
      set value of document property "Last Author" to "Ankit Ranjan"
      set value of document property "Title" to "BatchHelm AI - Qwen Global AI Hackathon"
      set value of document property "Subject" to "Production-shaped recall autopilot"
      set value of document property "Comments" to "BatchHelm hackathon presentation"
      save
      close
    end tell
  end tell
end run
```

Run only when Step 1 fails acceptance:

```bash
osascript "$SCRATCH/set-deck-metadata.applescript" "$DECK"
```

Do not directly mutate PPTX OOXML.

Execution note: this conditional step ran because the artifact export did not
contain the approved author properties. PowerPoint saved a replacement file
with Ankit Ranjan as both creator and last modifier.

- [x] **Step 3: Re-run metadata and attribution checks**

Run:

```bash
unzip -p "$DECK" docProps/core.xml > "$TMP/final-core.xml"
rg -n "Ankit Ranjan|BatchHelm AI|Production-shaped recall autopilot" \
  "$TMP/final-core.xml"
if rg -n "python-pptx|Steve Canny" "$TMP/final-core.xml"; then
  exit 1
fi
cd "$REPO"
./scripts/check-attribution.sh
```

Expected: only Ankit Ranjan is named as an individual author, and attribution checks pass.

- [x] **Step 4: Commit and push metadata cleanup when the PPTX changed**

Run:

```bash
cd "$REPO"
if ! git diff --quiet -- docs/presentation/batchhelm-ai-hackathon-deck.pptx; then
  git add docs/presentation/batchhelm-ai-hackathon-deck.pptx
  git commit --author="Ankit Ranjan <ankit0ranjan@gmail.com>" \
    -m "chore(presentation): finalize deck authorship metadata"
  git push origin main
fi
```

Expected: no metadata-only change is left uncommitted.

Execution note: the cleaned metadata shipped with the complete narrative in
commit `6427bbf`.

## Task 9: Run Full Visual And Structural Release Gates

**Files:**
- Read: `docs/presentation/batchhelm-ai-hackathon-deck.pptx`
- Create outside repository: `$TMP/final-render/`
- Create outside repository: `$TMP/final-inspect/`
- Create outside repository: `$TMP/final-montage.png`
- Create outside repository: `$TMP/qa/template-fidelity-check.json`

- [x] **Step 1: Render all ten final slides and create the montage**

Run:

```bash
rm -rf "$TMP/final-render" "$TMP/final-inspect"
mkdir -p "$TMP/final-render"
"$PYTHON" "$PRESENTATION_SKILL/container_tools/render_slides.py" \
  "$DECK" \
  --output_dir "$TMP/final-render"
"$PYTHON" "$PRESENTATION_SKILL/container_tools/create_montage.py" \
  --input_dir "$TMP/final-render" \
  --output_file "$TMP/final-montage.png"
```

Inspect the montage first, then each full-resolution slide. Acceptance: exactly ten slides; no clipping, overlap, unreadable crop, fake UI, unsupported badge, or one-line title wrap.

- [x] **Step 2: Run overflow and overlap diagnostics**

Run:

```bash
"$PYTHON" "$PRESENTATION_SKILL/container_tools/slides_test.py" "$DECK"
```

Expected: no overflow or unintended overlap errors. Review every intentional overlap reported for screenshots, bars, or diagram nodes.

- [x] **Step 3: Inspect placeholders and visible text**

Run:

```bash
"$NODE" "$PRESENTATION_SKILL/template_following_scripts/inspect_template_deck.mjs" \
  --workspace "$TMP/final-inspect" \
  --pptx "$DECK"
rg -n -i "placeholder|lorem|todo|tbd|public url|live qwen|customer deployment" \
  "$TMP/final-inspect"
```

Expected: no unresolved placeholder text and no unsupported live/deployment claim.

- [x] **Step 4: Validate template fidelity**

Run:

```bash
"$NODE" "$PRESENTATION_SKILL/template_following_scripts/check_template_fidelity.mjs" \
  --workspace "$TMP" \
  --starter-pptx "$TMP/template-starter.pptx" \
  --final-pptx "$DECK" \
  --map "$TMP/template-frame-map.json" \
  --starter-layout-dir "$TMP/template-starter-layout" \
  --final-layout-dir "$TMP/final-inspect/template-inspect/layouts" \
  --edit-dir "$SCRATCH"
```

Expected: all ten slide mappings pass and every added primitive remains inside its declared zone.

- [x] **Step 5: Verify final package structure and editability**

Run:

```bash
unzip -l "$DECK" | rg "ppt/slides/slide[0-9]+\\.xml"
unzip -p "$DECK" ppt/presentation.xml | rg -o "<p:sldId " | wc -l
```

Expected: the package contains exactly ten slide XML files and reports ten slide IDs.

## Task 10: Close The Deck Milestone

**Files:**
- Modify: `docs/superpowers/plans/2026-07-04-batchhelm-final-hackathon-deck.md`
- Modify only if needed: `docs/presentation/batchhelm-ai-hackathon-deck.pptx`

- [x] **Step 1: Mark each completed plan checkbox**

Update this file incrementally during execution. At release, every applicable checkbox must be checked and every conditional path must state whether it ran.

- [x] **Step 2: Run repository gates**

Run:

```bash
cd "$REPO"
git diff --check
./scripts/check-attribution.sh
git status --short
```

Expected: no accidental scratch/render files are tracked and only the plan completion update, if any, remains.

- [x] **Step 3: Commit and push the verified milestone**

Run:

```bash
git add \
  docs/presentation/batchhelm-ai-hackathon-deck.pptx \
  docs/superpowers/plans/2026-07-04-batchhelm-final-hackathon-deck.md
git commit --author="Ankit Ranjan <ankit0ranjan@gmail.com>" \
  -m "docs: verify final hackathon deck"
git push origin main
```

If the deck is unchanged at this step, stage and commit only the completed plan.

- [x] **Step 4: Verify the remote revision**

Run:

```bash
git status --short --branch
git log -1 --format='%H%n%an <%ae>%n%s'
gh run list --branch main --limit 3
```

Expected:

- local `main` matches `origin/main`;
- the latest commit is authored by `Ankit Ranjan <ankit0ranjan@gmail.com>`;
- the repository CI run for the final revision has started or completed successfully.

- [x] **Step 5: Record what this milestone does not complete**

The overall hackathon submission remains open until these separately approved milestones are finished:

- Alibaba Cloud deployment and verified public URL;
- captured live Qwen provider proof;
- demo video;
- final submission form and track selection.

Do not mark the overall BatchHelm hackathon goal complete when only this deck milestone is complete.
