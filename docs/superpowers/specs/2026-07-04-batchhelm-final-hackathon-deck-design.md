# BatchHelm Final Hackathon Deck Design

**Status:** Approved  
**Approved:** 2026-07-04  
**Owner:** Ankit Ranjan  
**Output:** `docs/presentation/batchhelm-ai-hackathon-deck.pptx`

## Communication Job

By the end of the deck, Qwen Global AI Hackathon judges should believe that
BatchHelm is a working, production-shaped recall autopilot where Qwen handles
uncertain evidence, typed systems control action, and human review protects
safety-critical decisions.

The deck must persuade across the published judging priorities:

1. technical depth and engineering;
2. innovation and model creativity;
3. problem value and impact;
4. presentation and documentation.

The primary track is **Autopilot Agent**. **Agent Society** is the secondary
track demonstrated by the nine-specialist execution graph.

## Approved Direction

The approved direction is **Proof-first command center**.

The deck opens with the real product rather than a text explanation. Real
intake and Mission Control screenshots establish credibility in the first
minute. Architecture, resilience, and benchmark evidence then explain why the
product is trustworthy and technically difficult.

This direction was selected over:

- an incident-documentary approach, which had a stronger human story but less
  room for engineering evidence;
- a systems-first approach, which emphasized architecture but risked feeling
  like an internal design review.

## Source Deck Contract

The existing 11-slide PowerPoint is the visual and structural source:

`docs/presentation/batchhelm-ai-hackathon-deck.pptx`

Implementation must use presentation template-following mode:

- inspect all inherited slides and objects;
- map every output slide to an inherited source slide;
- duplicate and edit inherited elements rather than rebuilding unrelated
  layouts over the source;
- preserve the source deck's 16:9 canvas and editable PowerPoint structure;
- replace sparse text-only content with the approved evidence-led narrative;
- remove inherited placeholders that are not intentionally filled.

The final deck contains ten slides. The extra source slide may be omitted when
the frame map documents the reason.

## Slide Narrative

### Slide 1 - A Recall Packet Becomes A Controlled Response

**Narrative job:** Establish the product and its category immediately.

Visible content:

- `BatchHelm`
- `A recall packet becomes a controlled response.`
- `Real intake. Nine specialist agents. Human evidence gate.`
- `Qwen Global AI Hackathon`
- `Ankit Ranjan`

Visual:

- dark command-teal title field;
- large crop of the populated Review workspace;
- no feature list, agenda, or deployment claim.

### Slide 2 - Recalls Create Five Unanswered Questions

**Narrative job:** Make the operational problem concrete.

The five questions are:

1. What product and lots are affected?
2. Where are matching units now?
3. Who must act?
4. Who may need notification?
5. What evidence must survive?

Visual:

- the committed supplier notice and shelf-evidence image;
- restrained recall-red signal;
- minimal copy explaining that small operators lack enterprise recall tooling.

The slide must not invent market-size figures or external customer claims.

### Slide 3 - Files, Review, Launch

**Narrative job:** Prove that ambiguous real-world intake exists.

Visible evidence:

- supplier PDF;
- invalid inventory CSV;
- uploaded cooler image;
- six accepted rows;
- two rejected rows;
- 23 on-hand units;
- two stores;
- two review warnings;
- field-level provenance and confidence.

Visual:

- populated Files and Review screenshots;
- a simple three-stage label, not a decorative process diagram.

### Slide 4 - Autonomy Stops At The Evidence Gate

**Narrative job:** Explain why the workflow can act without becoming reckless.

Claims:

- reviewer corrections become versioned evidence;
- stale reviewer versions return a conflict instead of overwriting newer work;
- confirmation creates an immutable incident snapshot;
- launch is blocked before confirmation;
- arbitrary image failure produces an unknown match and requires review.

Visual:

- crop showing provenance, confidence, warnings, and neutral shelf evidence;
- one human-review callout;
- no claim that authentication or RBAC is implemented.

### Slide 5 - Qwen Handles The Uncertain Work

**Narrative job:** Show that Qwen is the reasoning engine rather than a label on
the product.

Qwen responsibilities:

- text and rendered-page recall extraction;
- shelf-image interpretation;
- inventory-match reasoning;
- risk classification;
- customer communication;
- management briefing.

Engineering controls:

- structured JSON requests;
- Pydantic validation;
- explicit provider source;
- bounded retries;
- neutral or literal fallbacks;
- reviewer escalation.

Live-Qwen badges or latency figures may appear only after a real live run is
captured. Until then, the slide describes the implemented integration without
claiming live execution evidence.

### Slide 6 - Nine Specialists Share One Typed Blackboard

**Narrative job:** Explain the Agent Society and its parallel structure.

The slide shows six waves:

1. Recall Intake;
2. Document Extraction;
3. Inventory Matching and Shelf Vision;
4. Risk Scoring and Memory;
5. Operations Task and Communications;
6. Compliance Evidence.

Visual:

- compact native PowerPoint DAG with connectors behind nodes;
- Mission Control screenshot as supporting proof;
- no dense list of all class names or implementation files.

### Slide 7 - Every Event Survives Before It Appears

**Narrative job:** Prove production-shaped durability.

The slide distinguishes four persistence responsibilities:

- intake lifecycle and confirmed snapshots;
- immutable artifact files;
- orchestration runs, events, and checkpoints;
- memory and human review ledgers.

Claims:

- request UUID idempotency;
- persist-before-publish Server-Sent Events;
- replay after refresh;
- typed wave checkpoints;
- startup recovery for extraction and non-terminal runs;
- one API replica in the current SQLite lifecycle model.

Visual:

- one concise architecture diagram;
- separate stores remain visually separate;
- no implication that distributed workers or Postgres already exist.

### Slide 8 - The DAG Earns Its Complexity

**Narrative job:** Quantify why the Agent Society design matters.

Benchmark evidence:

- Agent Society mean: `1095.3 ms`;
- sequential baseline mean: `1633.9 ms`;
- DAG result: `1.49x faster`;
- forced Shelf Vision failure: `4/9` agents still complete versus baseline
  abort after `3/9`;
- simulated crash after wave four: DAG reruns `3/9` agents versus baseline
  rerunning `9/9`.

The latency benchmark must disclose that both arms use identical synthetic
180 ms per-agent delay in deterministic fallback mode to isolate orchestration
strategy from provider latency.

Visual:

- horizontal comparison bars for latency;
- two compact resilience comparisons;
- the conclusion must be written next to the evidence rather than left for the
  audience to infer.

### Slide 9 - The Sample Incident Proves Operational Value

**Narrative job:** Bring engineering back to the real recall.

Visible proof:

- two stores;
- 23 affected units;
- six valid inventory rows;
- two safely rejected rows;
- five affected lots;
- one optional shelf artifact;
- one durable run and 37 ordered events from browser verification.

Visual:

- inventory-review screenshot;
- shelf-evidence photo;
- compact evidence trail from notice to confirmed snapshot to run.

The slide must not present the synthetic packet as a real customer incident.

### Slide 10 - Built For The Path From Notice To Audit

**Narrative job:** Resolve the opening and give judges a concrete next action.

Visible content:

- `github.com/ankitranjan-dsai/batchhelm-ai`
- MIT license;
- green GitHub Actions evidence for backend, frontend, attribution, and Docker;
- Alibaba Cloud deployment architecture;
- `Ankit Ranjan`.

The close must not show a public application URL until one is deployed and
verified. It must not claim live Qwen proof until that evidence exists.

## Visual System

### Palette

- command teal: `#0B3D38`;
- active teal: `#087C72`;
- evidence white: `#F8FBFA`;
- dark text: `#132925`;
- muted text: `#5B6F6A`;
- recall signal: `#B42318`;
- review amber: `#C47A00`;
- border: `#D6E3DF`.

The deck must not become a one-note teal theme. Recall red and review amber are
used only when they communicate state. White and near-white evidence surfaces
remain dominant on content slides.

### Typography

- deck title: at least 50 pt;
- slide titles: at least 35 pt;
- mid-level callouts: at least 24 pt;
- body text: at least 16 pt;
- no negative letter spacing;
- no one-line title may wrap.

Copy must be direct, audience-facing, and written as claims rather than section
labels. Internal production notes, timing scaffolds, and presenter instructions
must not appear on slides.

### Composition

- one primary composition per slide;
- no nested cards or dashboard-style card grids;
- real screenshots and evidence images are the main visual assets;
- screenshots use readable crops rather than full-page thumbnails;
- diagrams are used only for the Agent Society and persistence architecture;
- connectors are created before nodes so they remain behind labels;
- no decorative gradients, orbs, stock illustrations, or fake product UI;
- no repeated screenshot on more than one slide unless a different crop proves
  a different claim.

## Source Assets

Approved repository assets:

- `docs/design-assets/screenshots/intake-files-desktop.png`;
- `docs/design-assets/screenshots/intake-review-desktop.png`;
- `docs/design-assets/screenshots/intake-review-mobile.png`;
- `docs/design-assets/screenshots/mission-control-desktop.png`;
- `sample-data/recall-notice-spinach.pdf`;
- `sample-data/store-b-cooler-spinach.png`;
- `docs/benchmarks/agent-society-vs-single-agent.md`;
- `docs/architecture.md`;
- latest successful GitHub Actions run for the final committed revision.

All product UI must come from real repository screenshots. No generated
approximation of the interface is allowed.

## Authorship And Attribution

- The visible author is `Ankit Ranjan`.
- PowerPoint document metadata must identify Ankit Ranjan as author when the
  export path supports metadata.
- The deck must contain no contributor-credit language.
- Qwen and Alibaba Cloud are credited only as technologies and service
  providers used by BatchHelm.
- Repository attribution checks must pass before commit.

## QA And Verification

Before delivery:

1. render every final slide to PNG;
2. inspect the complete montage and every full-size slide;
3. run overflow and overlap checks;
4. confirm every title remains one line;
5. confirm all screenshots are sharp and correctly cropped;
6. verify charts against the benchmark source;
7. inspect final PowerPoint XML for empty inherited placeholders;
8. run template-fidelity checks against the mapped starter deck;
9. scan visible text for unverified live-Qwen or deployment claims;
10. run `./scripts/check-attribution.sh` and `git diff --check`.

## Acceptance Criteria

The deck is complete when:

- it contains exactly ten coherent slides;
- slide one proves the product visually;
- the Files, Review, and Launch workflow is clear;
- provenance, human correction, and neutral fallback are visible;
- Qwen has specific, technically accurate responsibilities;
- all nine agents and six waves are represented;
- persistence responsibilities remain separate;
- benchmark figures match the reproducible source;
- the synthetic incident is labeled honestly;
- unverified deployment and live-model claims are absent;
- Ankit Ranjan is the only visible individual author;
- there are no unresolved placeholders, overflow, or unintended overlaps;
- the final PPTX renders successfully and remains editable.
