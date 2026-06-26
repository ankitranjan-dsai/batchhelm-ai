# BatchHelm Frontend Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working BatchHelm dashboard foundation as a React + Vite app that matches the approved command-center concept.

**Architecture:** The frontend lives in `apps/web` with focused React components, static sample data, shared domain types, and one global stylesheet built from `docs/design-system.md`. The first milestone is local-state driven so the product can demo immediately while the backend and Qwen provider are built next.

**Tech Stack:** React, Vite, TypeScript, lucide-react, CSS custom properties.

---

## File Structure

- Create `apps/web/package.json` for scripts and dependencies.
- Create `apps/web/index.html` as the Vite entry document.
- Create `apps/web/tsconfig.json`, `apps/web/tsconfig.node.json`, and `apps/web/vite.config.ts` for TypeScript and Vite.
- Create `apps/web/src/main.tsx` for React bootstrap.
- Create `apps/web/src/App.tsx` as the composition shell.
- Create `apps/web/src/data/demoIncident.ts` for synthetic recall data.
- Create `apps/web/src/types.ts` for domain interfaces.
- Create `apps/web/src/styles.css` for design tokens, layout, components, responsive states, and motion.

### Task 1: Scaffold React App

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/index.html`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/tsconfig.node.json`
- Create: `apps/web/vite.config.ts`
- Create: `apps/web/src/main.tsx`
- Create: `apps/web/src/vite-env.d.ts`

- [ ] **Step 1: Add Vite package metadata**

Create `apps/web/package.json` with scripts for `dev`, `build`, `preview`, and `typecheck`.

- [ ] **Step 2: Add TypeScript and Vite config**

Create strict TypeScript settings and a Vite React plugin config.

- [ ] **Step 3: Add React bootstrap**

Create a root document and mount `App` from `src/main.tsx`.

- [ ] **Step 4: Install dependencies**

Run: `npm install` from `apps/web`.

- [ ] **Step 5: Commit**

Run:

```bash
git add apps/web docs/superpowers/plans/2026-06-26-batchhelm-frontend-foundation.md
git commit -m "chore: scaffold BatchHelm web app"
```

### Task 2: Add Demo Domain Data

**Files:**
- Create: `apps/web/src/types.ts`
- Create: `apps/web/src/data/demoIncident.ts`

- [ ] **Step 1: Define domain interfaces**

Add typed models for incidents, metrics, workflow steps, inventory rows, task rows, evidence items, agent activity, memory insights, and milestones.

- [ ] **Step 2: Add synthetic recall scenario**

Add a spinach recall incident with two stores, six inventory rows, seven open tasks, evidence progress, live agent activity, memory insights, and milestone timers.

- [ ] **Step 3: Run typecheck**

Run: `npm run typecheck` from `apps/web`.

- [ ] **Step 4: Commit**

Run:

```bash
git add apps/web/src/types.ts apps/web/src/data/demoIncident.ts
git commit -m "feat: add recall incident demo data"
```

### Task 3: Build Dashboard Components

**Files:**
- Create: `apps/web/src/App.tsx`
- Create: `apps/web/src/styles.css`

- [ ] **Step 1: Build app shell**

Compose sidebar, top bar, summary panel, timeline, affected inventory, live agent activity, memory insights, task board, evidence progress, and milestones.

- [ ] **Step 2: Add local interactions**

Add selected navigation state, task completion toggles, active table filtering, and evidence progress recalculation from completed evidence items.

- [ ] **Step 3: Add accessible labels**

Use semantic landmarks, table headers, button labels, checkbox labels, and visible focus states.

- [ ] **Step 4: Run typecheck**

Run: `npm run typecheck` from `apps/web`.

- [ ] **Step 5: Commit**

Run:

```bash
git add apps/web/src/App.tsx apps/web/src/styles.css
git commit -m "feat: build recall command center dashboard"
```

### Task 4: Verify And Push

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add local frontend run instructions**

Document `cd apps/web`, `npm install`, `npm run dev`, and `npm run build`.

- [ ] **Step 2: Run production build**

Run: `npm run build` from `apps/web`.

- [ ] **Step 3: Start dev server**

Run: `npm run dev -- --host 127.0.0.1`.

- [ ] **Step 4: Capture browser screenshot**

Capture desktop and mobile screenshots for comparison against `docs/design-assets/batchhelm-dashboard-concept.png`.

- [ ] **Step 5: Push main**

Run:

```bash
git add README.md
git commit -m "docs: add web app run instructions"
git push
```

## Self-Review

- Spec coverage: Covers the frontend foundation, sample incident, dashboard interaction, verification, and run instructions from the product brief.
- Placeholder scan: The plan contains no TBD markers or undefined future tasks inside this milestone.
- Type consistency: Domain names in the plan match the intended React data modules.
