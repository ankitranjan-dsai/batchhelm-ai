import { demoIncident } from "./data/demoIncident";
import { getDemoKey } from "./auth";
import { randomId } from "./randomId";
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
export const evidencePacketDownloadUrl = `${API_BASE_URL}/api/v1/evidence/demo-packet.md`;

function authHeaders(): Record<string, string> {
  const key = getDemoKey();
  return key ? { "X-BatchHelm-Demo-Key": key } : {};
}

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

export interface OrchestrationRunView {
  run_id: string;
  incident_id: string;
  status: "pending" | "running" | "completed" | "failed";
  provider_mode: string;
  started_at: string | null;
  updated_at: string;
  finished_at: string | null;
  result: OrchestrationResult | null;
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
  provider: string;
  configured: boolean;
  mode: "live" | "demo-fallback";
}

export type ProviderProofState =
  | "verified"
  | "not-verified"
  | "unavailable";

export interface QwenVerificationReceipt {
  provider: "qwen-cloud";
  verified: true;
  model: string;
  latency_ms: number;
  response_sha256: string;
  verified_at: string;
}

export interface DashboardSync {
  provider: ProviderStatus;
  proof: QwenVerificationReceipt | null;
  proofState: ProviderProofState;
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
  recall_match: boolean | null;
  recommended_action: string;
  review_required: boolean;
  evidence_note: string;
  provider: string;
  used_fallback: boolean;
}

export type IntakeStatus =
  | "uploaded"
  | "extracting"
  | "review_required"
  | "ready"
  | "run_started"
  | "failed";

export interface InventoryItem {
  id: string;
  store: string;
  sku: string;
  product: string;
  lot: string;
  upc: string;
  on_hand: number;
  location: string;
  supplier_alias: string;
}

export interface RecallCriteriaDraft {
  product_name: string;
  affected_lots: string[];
  upcs: string[];
  risk_level: "low" | "medium" | "high" | "critical" | null;
  reason: string;
  source: string;
}

export interface InventoryImportSummary {
  accepted_rows: number;
  rejected_rows: number;
  stores: number;
  mapped_headers: Record<string, string>;
  warnings: string[];
}

export interface RecallIncidentDraft {
  criteria: RecallCriteriaDraft;
  notice_text: string;
  inventory: InventoryItem[];
  stores: string[];
  import_summary: InventoryImportSummary;
  shelf_inspection: ShelfInspectionResult | null;
  review_required: boolean;
}

export interface PublicIntakeArtifact {
  id: string;
  role: "recall_notice" | "inventory_csv" | "shelf_photo";
  original_filename: string;
  media_type: string;
  size_bytes: number;
  sha256: string;
}

export interface IntakeFieldEvidence {
  id: string;
  intake_id: string;
  field_path: string;
  value: unknown;
  artifact_id: string | null;
  locator: string;
  source: OutputSource;
  confidence: number;
  requires_review: boolean;
  supersedes_id: string | null;
  created_at: string;
}

export interface IntakeAccepted {
  intake_id: string;
  status: IntakeStatus;
  status_url: string;
  created_at: string;
}

export interface IntakeView {
  intake_id: string;
  status: IntakeStatus;
  version: number;
  provider_mode: string;
  created_at: string;
  updated_at: string;
  artifacts: PublicIntakeArtifact[];
  draft: RecallIncidentDraft | null;
  evidence: IntakeFieldEvidence[];
  incident_id: string | null;
  run_id: string | null;
  error_code: string | null;
  error_message: string | null;
}

export interface IntakeDraftUpdate {
  request_id: string;
  expected_version: number;
  criteria: RecallCriteriaDraft;
  inventory: InventoryItem[];
}

export interface IntakeConfirmRequest {
  request_id: string;
  expected_version: number;
}

export interface IntakeRunAccepted {
  intake: IntakeView;
  run: OrchestrationRunAccepted;
}

interface APIErrorPayload {
  code?: string;
  message?: string;
}

export class APIRequestError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "APIRequestError";
    this.status = status;
    this.code = code;
  }
}

export async function createIntakePacket(
  requestId: string,
  notice: File,
  inventory: File,
  shelfPhoto?: File,
): Promise<IntakeAccepted> {
  const formData = new FormData();
  formData.append("request_id", requestId);
  formData.append("notice", notice);
  formData.append("inventory", inventory);
  if (shelfPhoto !== undefined) {
    formData.append("shelf_photo", shelfPhoto);
  }
  const response = await fetch(`${API_BASE_URL}/api/v1/intakes`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });
  return responseJson<IntakeAccepted>(response, "Intake upload failed.");
}

export async function fetchIntake(
  statusUrl: string,
  signal?: AbortSignal,
): Promise<IntakeView> {
  const url = statusUrl.startsWith("http")
    ? statusUrl
    : `${API_BASE_URL}${statusUrl}`;
  const response = await fetch(url, { headers: authHeaders(), signal });
  return responseJson<IntakeView>(response, "Intake status request failed.");
}

export async function updateIntakeDraft(
  intakeId: string,
  request: IntakeDraftUpdate,
): Promise<IntakeView> {
  const response = await fetch(`${API_BASE_URL}/api/v1/intakes/${intakeId}/draft`, {
    method: "PATCH",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return responseJson<IntakeView>(response, "Intake update failed.");
}

export async function confirmIntake(
  intakeId: string,
  request: IntakeConfirmRequest,
): Promise<IntakeView> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/intakes/${intakeId}/confirm`,
    {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(request),
    },
  );
  return responseJson<IntakeView>(response, "Intake confirmation failed.");
}

export async function startIntakeRun(
  intakeId: string,
  requestId: string,
): Promise<IntakeRunAccepted> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/intakes/${intakeId}/runs`,
    {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ request_id: requestId }),
    },
  );
  return responseJson<IntakeRunAccepted>(response, "Agent launch failed.");
}

async function responseJson<T>(
  response: Response,
  fallbackMessage: string,
): Promise<T> {
  if (response.ok) {
    return (await response.json()) as T;
  }
  let payload: APIErrorPayload = {};
  try {
    payload = (await response.json()) as APIErrorPayload;
  } catch {
    // The public fallback remains stable when an upstream response is not JSON.
  }
  throw new APIRequestError(
    response.status,
    payload.code ?? "request_failed",
    payload.message ?? fallbackMessage,
  );
}

export async function fetchDashboardSync(): Promise<DashboardSync> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const providerRequest = fetch(`${API_BASE_URL}/api/v1/qwen/status`, { headers: authHeaders(), signal: controller.signal });
    const proofRequest = fetch(`${API_BASE_URL}/api/v1/qwen/proof`, { headers: authHeaders(), signal: controller.signal }).catch(
      () => null,
    );
    const [providerResponse, proofResponse] = await Promise.all([
      providerRequest,
      proofRequest,
    ]);

    if (!providerResponse.ok) {
      throw new Error(`Provider request failed with ${providerResponse.status}`);
    }

    const provider = (await providerResponse.json()) as ProviderStatus;
    if (proofResponse === null) {
      return { provider, proof: null, proofState: "unavailable" };
    }
    if (proofResponse.ok) {
      return {
        provider,
        proof: (await proofResponse.json()) as QwenVerificationReceipt,
        proofState: "verified",
      };
    }
    return {
      provider,
      proof: null,
      proofState:
        proofResponse.status === 404 ? "not-verified" : "unavailable",
    };
  } finally {
    clearTimeout(timeout);
  }
}

export async function startDemoRun(
  requestId: string,
): Promise<OrchestrationRunAccepted> {
  const response = await fetch(`${API_BASE_URL}/api/v1/incidents/demo/runs`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ request_id: requestId }),
  });
  if (!response.ok) {
    throw new Error(`Run start failed with ${response.status}`);
  }
  return (await response.json()) as OrchestrationRunAccepted;
}

export async function fetchLatestRun(
  signal?: AbortSignal,
): Promise<OrchestrationRunView | null> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/orchestration/runs/latest`,
    { headers: authHeaders(), signal },
  );
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Latest run request failed with ${response.status}`);
  }
  return (await response.json()) as OrchestrationRunView;
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
  const response = await fetch(`${API_BASE_URL}/api/v1/memory`, { headers: authHeaders() });
  if (!response.ok) {
    throw new Error(`Memory request failed with ${response.status}`);
  }
  return (await response.json()) as MemoryRecord[];
}

export async function fetchDemoInspection(signal?: AbortSignal): Promise<ShelfInspectionResult> {
  const response = await fetch(`${API_BASE_URL}/api/v1/inspections/demo`, { headers: authHeaders(), signal });
  if (!response.ok) {
    throw new Error(`Demo inspection request failed with ${response.status}`);
  }

  return (await response.json()) as ShelfInspectionResult;
}

export async function uploadShelfPhoto(file: File, signal?: AbortSignal): Promise<ShelfInspectionResult> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/v1/inspections/shelf-photo`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
    signal,
  });
  if (!response.ok) {
    throw new Error(`Shelf inspection request failed with ${response.status}`);
  }

  return (await response.json()) as ShelfInspectionResult;
}

export async function fetchEvidencePacket(signal?: AbortSignal): Promise<EvidencePacket> {
  const response = await fetch(`${API_BASE_URL}/api/v1/evidence/demo-packet`, { headers: authHeaders(), signal });
  if (!response.ok) {
    throw new Error(`Evidence packet request failed with ${response.status}`);
  }

  return (await response.json()) as EvidencePacket;
}

export async function fetchEvidenceReview(signal?: AbortSignal): Promise<EvidenceReviewState> {
  const response = await fetch(`${API_BASE_URL}/api/v1/evidence/demo-review`, { headers: authHeaders(), signal });
  if (!response.ok) {
    throw new Error(`Evidence review request failed with ${response.status}`);
  }

  return (await response.json()) as EvidenceReviewState;
}

export async function submitReviewDecision(
  decision: ReviewDecision,
  signal?: AbortSignal,
): Promise<EvidenceReviewState> {
  const response = await fetch(`${API_BASE_URL}/api/v1/evidence/demo-review/decision`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({
      request_id: randomId(),
      reviewer: "Operations Manager",
      decision,
      note:
        decision === "approved"
          ? "Approved for supplier submission."
          : "Resolve open evidence blockers before submission.",
    }),
    signal,
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
