# BatchHelm AI Design System

Reference concept: `docs/design-assets/batchhelm-dashboard-concept.png`

## Product Feel

BatchHelm should feel like a premium operations console: calm, dense, trustworthy, and fast to scan. The interface is designed for managers responding to urgent recall events, so visual drama should come from status clarity and workflow progression rather than decorative effects.

## Layout

- Fixed left navigation rail with product mark, primary sections, system status, help, and settings.
- Top utility bar with search, incident status, notifications, and user profile.
- Main grid with recall summary, workflow timeline, affected inventory, task board, evidence progress, and milestone panels.
- Right rail for live agent activity and memory insights.
- Mobile layout should prioritize incident status, barcode/photo scan, affected/safe/uncertain decision, and task confirmation.

## Color Tokens

- Background: `#f7fafb`
- Surface: `#ffffff`
- Sidebar: `#052d3b`
- Sidebar active: `#087e7d`
- Text primary: `#082033`
- Text secondary: `#536778`
- Border: `#dce7eb`
- Accent teal: `#078b84`
- Accent teal soft: `#e4f6f4`
- Risk red: `#d92323`
- Risk red soft: `#ffe9e7`
- Warning amber: `#d98200`
- Warning amber soft: `#fff2d8`
- Success green: `#078a5b`
- Neutral gray: `#edf2f4`

## Typography

- Font stack: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif.
- Headline: 28-32px, 700 weight, tight but readable line-height.
- Section title: 12-14px, 700 weight, uppercase or high-contrast label.
- Table text: 13-14px, 500 weight.
- Metadata: 12px, 500 weight.
- Buttons and controls: 13-14px, 600 weight.

## Components

- Navigation item: icon plus label, 8px radius, selected teal surface.
- Summary metric: label, large value, supporting caption, vertical divider.
- Status pill: compact semantic color, 6px radius, icon when meaningful.
- Timeline row: status dot, title, caption, timestamp, completion marker.
- Data table: fixed row heights, subtle dividers, no card-grid replacement.
- Task row: checkbox, task, store, priority, assignee, due time, state.
- Evidence ring: circular progress plus checklist.
- Agent activity item: icon avatar, agent name, state pill, current action, time.
- Memory insight: icon, title, confidence or impact detail, view action.

## Motion

Use short, practical motion:

- 120-180ms hover and focus transitions
- timeline progress fade-in
- task completion state change
- drawer or panel transitions under 220ms

Respect `prefers-reduced-motion`.

## Avoid

- marketing hero sections
- long scrolling landing pages
- generic chatbot UI
- decorative gradients, orbs, and bokeh
- nested cards
- low-contrast tiny table text
- visible tooling attribution
