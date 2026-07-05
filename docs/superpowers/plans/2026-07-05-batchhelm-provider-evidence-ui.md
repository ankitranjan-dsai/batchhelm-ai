# BatchHelm Provider Evidence UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make persisted live-Qwen proof inspectable inside the BatchHelm
dashboard without confusing configured mode, deterministic fallback, or
provider failure with verified execution.

**Architecture:** Extend the existing dashboard synchronization request to load
provider status and the public redacted proof in parallel. A focused
`ProviderEvidenceControl` owns the compact top-bar status and accessible detail
dialog. The component renders five explicit states: loading, verified,
configured but not verified, fallback, and unavailable.

**Tech Stack:** React 18, TypeScript, Vite, Vitest, Testing Library, lucide-react,
existing BatchHelm CSS design tokens

---

## Design Contract

- Preserve the existing top-bar height, density, six-pixel radius family, and
  teal/amber/neutral semantic palette.
- Use a real button with a cloud/security icon, not a static status chip.
- The collapsed control shows `Qwen Cloud` and one state word.
- The dialog may show only redacted receipt fields already public through
  `/api/qwen/proof`.
- `mode: live` without a receipt renders `Configured`, never `Verified`.
- `demo-fallback` renders `Fallback`.
- A failed proof fetch renders `Unavailable` without taking the entire
  dashboard offline.
- The dialog closes by close button, backdrop click, and Escape.
- Mobile keeps a compact icon/state control and a dialog that fits 320 px.

## Task 1: Extend The Provider Synchronization Contract

**Files:**
- Create: `apps/web/src/api.test.ts`
- Modify: `apps/web/src/api.ts`

- [ ] **Step 1: Write failing API client tests**

Add tests for:

```typescript
expect(sync.proofState).toBe("verified");
expect(sync.proof?.provider_request_id).toBe("chatcmpl-proof");
```

Also require:

- HTTP `404` from `/api/qwen/proof` becomes `not-verified` with `proof: null`;
- other proof failures become `unavailable` without discarding provider status;
- provider status and proof requests start in parallel.

- [ ] **Step 2: Run the tests and verify the old contract fails**

Run:

```bash
cd apps/web
npm test -- src/api.test.ts
```

Expected: failures because `DashboardSync` has no proof fields and the client
does not request `/api/qwen/proof`.

- [ ] **Step 3: Add proof types and parallel fetching**

Add:

```typescript
export type ProviderProofState =
  | "verified"
  | "not-verified"
  | "unavailable";

export interface QwenVerificationReceipt {
  provider: "qwen-cloud";
  verified: true;
  model: string;
  base_url: string;
  provider_request_id: string | null;
  latency_ms: number;
  response_sha256: string;
  verified_at: string;
}

export interface DashboardSync {
  provider: ProviderStatus;
  proof: QwenVerificationReceipt | null;
  proofState: ProviderProofState;
}
```

Start both fetches before awaiting either response. Treat proof `404` as a
valid empty state and other proof failures as a degraded proof state.

- [ ] **Step 4: Verify the client contract**

Run:

```bash
cd apps/web
npm test -- src/api.test.ts
```

Expected: all API client tests pass.

## Task 2: Build The Accessible Evidence Control

**Files:**
- Create: `apps/web/src/ProviderEvidenceControl.tsx`
- Create: `apps/web/src/ProviderEvidenceControl.test.tsx`

- [ ] **Step 1: Write failing verified-state tests**

Render the component with a live provider and receipt. Require:

- button accessible name `Qwen Cloud evidence: verified`;
- visible collapsed state `Verified`;
- clicking opens a `dialog` named `Qwen Cloud evidence`;
- dialog shows model, provider request ID, latency, UTC timestamp, endpoint,
  and response fingerprint;
- credentials and response content are absent.

- [ ] **Step 2: Write failing degraded-state tests**

Require:

- live provider plus no receipt renders `Configured`;
- fallback provider renders `Fallback`;
- unavailable proof renders `Unavailable`;
- loading renders `Checking`;
- close button and Escape dismiss the dialog.

- [ ] **Step 3: Run tests and verify the component is missing**

Run:

```bash
cd apps/web
npm test -- src/ProviderEvidenceControl.test.tsx
```

Expected: import failure because the component does not exist.

- [ ] **Step 4: Implement the component**

Use `Cloud`, `ShieldCheck`, `AlertTriangle`, and `X` from `lucide-react`.
Keep state derivation in a small pure function and hoist static labels outside
the component. Use a native button and `role="dialog"` with
`aria-modal="true"`.

- [ ] **Step 5: Verify all component states**

Run:

```bash
cd apps/web
npm test -- src/ProviderEvidenceControl.test.tsx
```

Expected: all evidence-control tests pass.

## Task 3: Integrate The Control Into The Dashboard

**Files:**
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/styles.css`

- [ ] **Step 1: Add dashboard proof state**

Store:

```typescript
const [providerProof, setProviderProof] =
  useState<QwenVerificationReceipt | null>(null);
const [providerProofState, setProviderProofState] =
  useState<ProviderEvidenceState>("loading");
```

On successful synchronization, set provider, proof, and proof state. On status
failure, set the evidence state to `unavailable`.

- [ ] **Step 2: Replace the static provider chip**

Render `ProviderEvidenceControl` in `TopBar`. Keep the incident status,
notification button, and profile control unchanged.

- [ ] **Step 3: Add design-system-consistent styles**

Add:

- a stable 132 px collapsed control;
- green verified, amber configured/unavailable, and neutral fallback states;
- fixed-position modal backdrop;
- maximum 520 px dialog width with a structured definition list;
- monospace request ID and fingerprint with safe wrapping;
- 320 px responsive behavior;
- focus, hover, and reduced-motion behavior.

- [ ] **Step 4: Run frontend tests and build**

Run:

```bash
cd apps/web
npm test
npm run build
```

Expected: all tests, TypeScript checks, and the Vite build pass.

## Task 4: Verify The Product Visually

**Files:**
- Create outside repository: provider evidence screenshots

- [ ] **Step 1: Start the existing local stack**

Run the backend and frontend on available local ports. Use the deterministic
fallback configuration because no Qwen key is present.

- [ ] **Step 2: Verify the desktop interaction**

In the in-app browser:

1. load the dashboard;
2. confirm the collapsed state is `Fallback`;
3. open the evidence dialog;
4. confirm the dialog is legible and does not shift the top bar;
5. close it with Escape.

- [ ] **Step 3: Verify the mobile interaction**

At 390 x 844:

- the top bar does not overlap;
- the evidence button remains reachable;
- dialog content wraps without horizontal scrolling;
- close control remains visible.

- [ ] **Step 4: Inspect screenshots**

Use `view_image` on desktop and mobile captures. Check:

- top-bar density;
- semantic color;
- button/icon alignment;
- dialog hierarchy;
- long-value wrapping;
- absence of overlap.

## Task 5: Document, Commit, And Push

**Files:**
- Modify: `README.md`
- Modify: `docs/demo-script.md`
- Modify: `docs/submission-checklist.md`
- Modify: `docs/superpowers/plans/2026-07-05-batchhelm-provider-evidence-ui.md`

- [ ] **Step 1: Document the judge-facing control**

State that the top-bar evidence control distinguishes configured mode from a
persisted successful live receipt and exposes only redacted metadata.

- [ ] **Step 2: Keep external evidence honest**

Do not mark live verification, public URL, screenshots, video, or Devpost
submission complete. Mark only the in-product proof surface complete.

- [ ] **Step 3: Run release gates**

Run:

```bash
cd services/api
.venv/bin/pytest -q
cd ../../apps/web
npm test
npm run build
cd ../..
./scripts/check-attribution.sh
git diff --check
```

Expected: backend, frontend, attribution, and diff checks pass.

- [ ] **Step 4: Commit and push**

Run:

```bash
git add apps/web README.md docs
git commit --author="Ankit Ranjan <ankit0ranjan@gmail.com>" \
  -m "feat(web): expose redacted Qwen verification evidence"
git push origin main
```

- [ ] **Step 5: Verify remote CI**

Run:

```bash
git status --short --branch
git log -1 --format='%H%n%an <%ae>%n%s'
git ls-remote origin refs/heads/main
gh run list --branch main --limit 3
```

Expected: local and remote `main` match, author and committer are Ankit Ranjan,
and all CI jobs pass.

