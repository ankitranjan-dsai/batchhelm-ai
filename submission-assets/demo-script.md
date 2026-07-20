# BatchHelm AI Demo Video

Target length: under 3 minutes

Public demo: http://47.84.199.208/

Repository: https://github.com/ankitranjan-dsai/batchhelm-ai

## Shot List and Narration

1. Title

   This is BatchHelm AI, a recall operations command center deployed on Alibaba Cloud ECS. It turns an incident packet into an auditable, coordinated response, with Qwen at the center of extraction, reasoning, vision, and management briefing.

2. Qwen Cloud evidence

   The live application exposes a Qwen Cloud evidence receipt. This session verified qwen3.7-plus against Alibaba Cloud Model Studio, including the verification time, latency, and response fingerprint.

3. Recall intake

   A manager starts with the original recall notice, structured inventory CSV, and an optional shelf image. BatchHelm preserves the uploaded files and their provenance before processing.

4. Inventory impact

   For this spinach incident, the authoritative inventory match found 23 affected units across two stores and quarantined every matching lot.

5. Agent orchestration

   The orchestration service runs nine specialist agents as a dependency graph, in parallel waves. Every event is persisted, with retries and typed checkpoints, so a run can recover and replay without losing its audit trail.

6. Inventory Matching and Shelf Vision

   Here, Inventory Matching reconciles 23 units and supplier aliases. Shelf Vision uses Qwen to read the real shelf image, identify lot L2418, and return a 100 percent confidence recall match.

7. Staff task board

   The Operations Task agent turns those decisions into an accountable staff task board, with owners, due times, stores, and completion state.

8. Human approval

   Before anything leaves the organization, a human approval gate checks the inventory impact, communications, disposal records, and regulatory filing package.

9. Vision evidence

   The same Qwen vision result is preserved as evidence, including product, lot, UPC, confidence, recommended action, model source, and input filename.

10. Learned memory

    The Memory agent persists decisions and supplier aliases so future recalls can reuse learned patterns while still keeping human review in control.

11. Architecture

    The architecture is intentionally compact. React and FastAPI run in Docker on ECS, Qwen text and vision come from Alibaba Cloud Model Studio, and SQLite-backed stores preserve artifacts, events, reviews, and memory.

12. Alibaba Cloud proof

    This Alibaba Cloud console view shows the live ECS instance running in Singapore with normal health and public IP 47.84.199.208, the same address serving the demo.

13. Closing

    BatchHelm AI makes recall response faster, traceable, recoverable, and ready for human-approved submission. Thank you.

