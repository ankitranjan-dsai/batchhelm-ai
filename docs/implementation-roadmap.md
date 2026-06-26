# BatchHelm AI Implementation Roadmap

## Milestone 0: Project Foundation

- Establish repository, license, README, architecture, and product brief.
- Define environment variables and author metadata.
- Add sample recall scenario files.

## Milestone 1: Interactive Frontend Prototype

- Create React + Vite + TypeScript app.
- Build premium SaaS dashboard shell.
- Implement recall inbox, incident overview, agent timeline, affected inventory table, and task board using local sample data.
- Add responsive mobile shelf-inspection view.

## Milestone 2: Backend And Workflow Core

- Create FastAPI service.
- Define typed domain models for incidents, products, recall criteria, evidence, tasks, and agent outputs.
- Implement local persistence.
- Add workflow state transitions and audit events.

## Milestone 3: Qwen Integration

- Implement Qwen gateway with text and vision calls.
- Add structured recall-notice extraction.
- Add invoice and inventory matching.
- Add shelf-photo inspection.
- Provide mocked provider tests and graceful fallback behavior for demo mode.

## Milestone 4: Agent Society

- Implement specialist agents with explicit responsibilities.
- Add orchestration that runs independent agents in parallel where possible.
- Show live agent status in the dashboard.
- Persist memory for supplier aliases and repeated decisions.

## Milestone 5: Evidence Packet And Demo Assets

- Generate Markdown and PDF-ready evidence packets.
- Add customer notice and staff instruction drafts.
- Add architecture diagram, API docs, deployment guide, demo script, screenshots, and sample data.

## Milestone 6: Deployment And Submission Polish

- Add Dockerfile and deployment guide for Alibaba Cloud.
- Run lint, tests, and production build.
- Capture final screenshots.
- Prepare submission checklist and demo walkthrough.
