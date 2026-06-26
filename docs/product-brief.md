# BatchHelm AI Product Brief

## One-Line Pitch

BatchHelm AI is an autonomous command center that helps small operators execute product recalls across inventory, shelves, staff tasks, customer notices, and evidence packets.

## Problem

Product recalls are time-sensitive and operationally messy. A manager may need to read recall notices, search supplier invoices, compare lot codes, inspect physical shelves, remove products, notify customers, preserve evidence, and report status to leadership or suppliers.

Large enterprises may have formal recall tooling. Small grocery stores, restaurants, pharmacies, cafeterias, and local distributors often rely on email, spreadsheets, staff memory, and ad hoc photos. That creates four risks:

- missed affected stock
- slow response time
- weak evidence trail
- inconsistent customer communication

## Target Users

- Independent grocery operators
- Small regional grocery chains
- Restaurants and cafes with supplier-managed inventory
- Pharmacies and health stores
- School or office cafeterias
- Local distributors and wholesalers

## Core User Story

As a store operations manager, I want to upload a recall notice, invoices, inventory data, and shelf photos so BatchHelm can determine whether we are affected, guide staff through response tasks, and generate a defensible evidence packet.

## Demo Scenario

An active recall notice covers a spinach product with specific UPC, lot-code, and best-by date ranges. The demo store has two locations, incomplete inventory data, three supplier invoices, and several shelf photos.

BatchHelm should:

1. extract structured recall criteria from the notice
2. match supplier invoice rows with fuzzy product aliases
3. inspect shelf photos for brand, pack size, UPC, lot code, and best-by date
4. produce confidence-scored affected-product decisions
5. create removal and quarantine tasks for staff
6. draft a customer notification
7. compile an evidence packet with timestamps and unresolved items

## Differentiators

- Product-recall workflow, not generic document chat
- Multi-agent task execution with visible responsibility boundaries
- Multimodal reasoning over documents, tables, and shelf photos
- Persistent operational memory for product aliases and store layouts
- Evidence-first design suitable for stressful, regulated workflows

## Success Criteria

- Judges understand the value in under one minute.
- The app shows an end-to-end incident response, not a static mockup.
- Qwen model calls produce structured outputs used by the workflow.
- The UI feels like a premium SaaS operations product.
- The repository includes clear setup, API, architecture, deployment, and demo documentation.
