import { demoIncident } from "./data/demoIncident";
import type {
  AgentActivity,
  EvidenceItem,
  EvidencePacket,
  EvidenceReviewState,
  InventoryRow,
  MemoryInsight,
  Milestone,
  RecallIncident,
  RecallMetric,
  ReviewDecision,
  StaffTask,
  WorkflowStep,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
export const evidencePacketDownloadUrl = `${API_BASE_URL}/api/evidence/demo-packet.md`;

export type OutputSource = "qwen" | "deterministic" | "memory" | "reviewer";

export interface AgentRunResult {
  agent: string;
  role: string;
  status: "completed" | "failed" | "skipped" | "running" | "pending";
  summary: string;
  reasoning: string;
  confidence: number;
  source: OutputSource;
  used_fallback: boolean;
  provider: string;
  model: string;
  attempts: number;
  duration_ms: number;
  depends_on: string[];
}

export interface AgentRunEvent {
  id: string;
  run_id: string;
  sequence: number;
  agent: string;
  type:
    | "started"
    | "reasoning"
    | "output"
    | "completed"
    | "failed"
    | "retry"
    | "conflict"
    | "resolved"
    | "checkpoint"
    | "orchestrator";
  message: string;
  at: string;
  source: OutputSource;
  data?: Record<string, unknown> | null;
}

export interface ManagementBriefing {
  headline: string;
  situation: string;
  actions: string[];
  risks: string[];
  next_review: string;
  confidence: number;
  source: OutputSource;
  provider: string;
  used_fallback: boolean;
}

export interface OrchestrationResult {
  run_id: string;
  incident_id: string;
  status: "completed" | "failed";
  provider_mode: "live" | "demo-fallback";
  started_at: string;
  finished_at: string;
  duration_ms: number;
  agents: AgentRunResult[];
  events: AgentRunEvent[];
  analysis: BackendAnalysis;
  briefing: ManagementBriefing;
  memory_writes: number;
  conflicts_resolved: number;
  summary: string;
}

export interface OrchestrationRunAccepted {
  run_id: string;
  incident_id: string;
  status: "pending" | "running" | "completed" | "failed";
  events_url: string;
  result_url: string;
}

export interface MemoryRecord {
  id: string;
  kind: string;
  key: string;
  value: string;
  detail: string;
  confidence: number;
  occurrences: number;
  first_seen: string;
  last_seen: string;
  source: OutputSource;
}

interface BackendAnalysis {
  incident_id: string;
  product: string;
  lot_range: string;
  risk_level: "low" | "medium" | "high" | "critical";
  affected_stores: string[];
  affected_items: number;
  open_tasks: number;
  evidence_progress: number;
  workflow: WorkflowStep[];
  inventory: BackendInventoryRow[];
  tasks: StaffTask[];
  evidence: EvidenceItem[];
  agents: AgentActivity[];
  insights: MemoryInsight[];
  milestones: Milestone[];
}

interface BackendInventoryRow {
  id: string;
  store: string;
  sku: string;
  product: string;
  lot: string;
  on_hand: number;
  quarantined: number;
  confidence: number;
  status: "quarantined" | "review" | "clear";
  location: string;
}

export interface ProviderStatus {
  configured: boolean;
  mode: "live" | "demo-fallback";
  text_model: string;
  vision_model: string;
}

export interface DashboardSync {
  provider: ProviderStatus;
}

export interface ShelfInspectionResult {
  upload: {
    original_filename: string;
    media_type: string;
    size_bytes: number;
  };
  extracted: {
    product_name: string;
    lot_code: string;
    upc: string;
    best_by: string | null;
    confidence: number;
  };
  recall_match: boolean;
  recommended_action: string;
  review_required: boolean;
  evidence_note: string;
  provider: string;
  used_fallback: boolean;
}

export async function fetchDashboardSync(): Promise<DashboardSync> {
  const providerResponse = await fetch(`${API_BASE_URL}/api/qwen/status`);
  if (!providerResponse.ok) {
    throw new Error(`Provider request failed with ${providerResponse.status}`);
  }

  const provider = (await providerResponse.json()) as ProviderStatus;
  return { provider };
}

export async function startDemoRun(
  requestId: string,
): Promise<OrchestrationRunAccepted> {
  const response = await fetch(`${API_BASE_URL}/api/incidents/demo/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ request_id: requestId }),
  });
  if (!response.ok) {
    throw new Error(`Run start failed with ${response.status}`);
  }
  return (await response.json()) as OrchestrationRunAccepted;
}

export function orchestrationEventsUrl(
  accepted: OrchestrationRunAccepted,
  after = 0,
): string {
  const base = accepted.events_url.startsWith("http")
    ? accepted.events_url
    : `${API_BASE_URL}${accepted.events_url}`;
  return after > 0 ? `${base}?after=${after}` : base;
}

export async function fetchMemoryRecords(): Promise<MemoryRecord[]> {
  const response = await fetch(`${API_BASE_URL}/api/memory`);
  if (!response.ok) {
    throw new Error(`Memory request failed with ${response.status}`);
  }
  return (await response.json()) as MemoryRecord[];
}

export async function fetchDemoInspection(): Promise<ShelfInspectionResult> {
  const response = await fetch(`${API_BASE_URL}/api/inspections/demo`);
  if (!response.ok) {
    throw new Error(`Demo inspection request failed with ${response.status}`);
  }

  return (await response.json()) as ShelfInspectionResult;
}

export async function uploadShelfPhoto(file: File): Promise<ShelfInspectionResult> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/inspections/shelf-photo`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(`Shelf inspection request failed with ${response.status}`);
  }

  return (await response.json()) as ShelfInspectionResult;
}

export async function fetchEvidencePacket(): Promise<EvidencePacket> {
  const response = await fetch(`${API_BASE_URL}/api/evidence/demo-packet`);
  if (!response.ok) {
    throw new Error(`Evidence packet request failed with ${response.status}`);
  }

  return (await response.json()) as EvidencePacket;
}

export async function fetchEvidenceReview(): Promise<EvidenceReviewState> {
  const response = await fetch(`${API_BASE_URL}/api/evidence/demo-review`);
  if (!response.ok) {
    throw new Error(`Evidence review request failed with ${response.status}`);
  }

  return (await response.json()) as EvidenceReviewState;
}

export async function submitReviewDecision(
  decision: ReviewDecision,
): Promise<EvidenceReviewState> {
  const response = await fetch(`${API_BASE_URL}/api/evidence/demo-review/decision`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      request_id: crypto.randomUUID(),
      reviewer: "Operations Manager",
      decision,
      note:
        decision === "approved"
          ? "Approved for supplier submission."
          : "Resolve open evidence blockers before submission.",
    }),
  });
  if (!response.ok) {
    throw new Error(`Evidence review decision failed with ${response.status}`);
  }

  return (await response.json()) as EvidenceReviewState;
}

export function toIncident(analysis: BackendAnalysis): RecallIncident {
  const metrics: RecallMetric[] = [
    {
      label: "Risk Level",
      value: titleCase(analysis.risk_level),
      detail: "Health hazard risk",
      tone: "risk",
    },
    {
      label: "Affected Stores",
      value: String(analysis.affected_stores.length),
      detail: analysis.affected_stores.join(", "),
    },
    {
      label: "Affected Items",
      value: String(analysis.affected_items),
      detail: "Total SKUs/items",
    },
    {
      label: "Open Tasks",
      value: String(analysis.open_tasks),
      detail: "Across all stores",
      tone: "warning",
    },
    {
      label: "Evidence Progress",
      value: `${analysis.evidence_progress}%`,
      detail: "Packet readiness",
      tone: "success",
    },
  ];

  return {
    ...demoIncident,
    id: analysis.incident_id,
    product: analysis.product,
    lotRange: analysis.lot_range,
    riskLevel: analysis.risk_level,
    stores: analysis.affected_stores,
    metrics,
    workflow: analysis.workflow,
    inventory: analysis.inventory.map(toInventoryRow),
    tasks: analysis.tasks,
    evidence: analysis.evidence,
    agents: analysis.agents,
    insights: analysis.insights,
    milestones: analysis.milestones,
  };
}

function toInventoryRow(row: BackendInventoryRow): InventoryRow {
  return {
    id: row.id,
    store: row.store,
    sku: row.sku,
    product: row.product,
    lot: row.lot,
    onHand: row.on_hand,
    quarantined: row.quarantined,
    confidence: row.confidence,
    status: row.status,
    location: row.location,
  };
}

function titleCase(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
