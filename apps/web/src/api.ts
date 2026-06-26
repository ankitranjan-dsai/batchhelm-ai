import { demoIncident } from "./data/demoIncident";
import type {
  AgentActivity,
  EvidenceItem,
  EvidencePacket,
  InventoryRow,
  MemoryInsight,
  Milestone,
  RecallIncident,
  RecallMetric,
  StaffTask,
  WorkflowStep,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
export const evidencePacketDownloadUrl = `${API_BASE_URL}/api/evidence/demo-packet.md`;

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
  incident: RecallIncident;
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
  const [analysisResponse, providerResponse] = await Promise.all([
    fetch(`${API_BASE_URL}/api/incidents/demo/analyze`, { method: "POST" }),
    fetch(`${API_BASE_URL}/api/qwen/status`),
  ]);

  if (!analysisResponse.ok) {
    throw new Error(`Analysis request failed with ${analysisResponse.status}`);
  }
  if (!providerResponse.ok) {
    throw new Error(`Provider request failed with ${providerResponse.status}`);
  }

  const analysis = (await analysisResponse.json()) as BackendAnalysis;
  const provider = (await providerResponse.json()) as ProviderStatus;

  return {
    incident: toIncident(analysis),
    provider,
  };
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

function toIncident(analysis: BackendAnalysis): RecallIncident {
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
