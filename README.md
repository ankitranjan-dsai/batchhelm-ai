# BatchHelm AI

**BatchHelm AI is an autonomous recall command center for product batches, shelves, and store teams.**

When a food or consumer-product recall arrives, small operators need to know whether they are affected, where the product is, who needs to act, who may need to be notified, and what evidence must be retained. BatchHelm turns recall notices, invoices, inventory files, shelf photos, and task completion records into a coordinated response workflow.

## Vision

BatchHelm is designed for small grocery chains, restaurants, pharmacies, cafeterias, and distributors that do not have enterprise recall-management tooling. The product focuses on urgent operational clarity:

- identify affected products and batches
- match recall notices against invoices, POS exports, and catalog data
- inspect shelf or stockroom photos for labels, dates, UPCs, and lot codes
- create removal, quarantine, disposal, refund, and customer-notice tasks
- preserve evidence in an audit-ready packet
- remember supplier aliases, store layouts, historical decisions, and recurring false positives

## Hackathon Track Fit

BatchHelm is designed for the Qwen Global AI Hackathon and uses Qwen Cloud models through an OpenAI-compatible API layer.

- **Autopilot Agent:** runs the recall response workflow from intake to resolution.
- **Agent Society:** specialist agents divide recall parsing, inventory matching, image inspection, operations coordination, communications, and compliance packet generation.
- **MemoryAgent:** stores supplier naming patterns, product aliases, store layouts, and previous recall outcomes.
- **EdgeAgent:** supports in-store shelf inspection from a mobile device with resilient upload and queued review.
- **AI Showrunner:** can generate a short management briefing that summarizes incident progress and next actions.

## Initial Product Surface

The first release will be a premium operations dashboard with these core screens:

- Recall inbox and incident details
- Affected inventory map
- Agent workflow timeline
- Shelf-photo inspection queue
- Staff task board
- Customer notice composer
- Evidence packet preview
- Memory and alias manager

## Technology Direction

- Frontend: React, Vite, TypeScript
- Backend: FastAPI, Python, Pydantic
- Model integration: Qwen Cloud via configurable provider interface
- Storage: SQLite for local demo, Postgres-ready repository layer
- Documents: generated Markdown/PDF evidence packet
- Deployment target: Alibaba Cloud Container Service or Elastic Compute Service with Docker

## Author

Ankit Ranjan

## License

MIT
