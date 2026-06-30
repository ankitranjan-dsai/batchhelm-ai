export type Severity = "low" | "medium" | "high" | "critical";

export type WorkflowStatus = "complete" | "active" | "waiting" | "pending";

export type TaskStatus = "not-started" | "in-progress" | "blocked" | "complete";

export type EvidenceStatus = "completed" | "in-progress" | "pending";

export interface RecallMetric {
  label: string;
  value: string;
  detail: string;
  tone?: "risk" | "success" | "warning" | "neutral";
}

export interface RecallIncident {
  id: string;
  title: string;
  product: string;
  lotRange: string;
  riskLevel: Severity;
  riskDetail: string;
  status: "active" | "monitoring" | "resolved";
  openedAt: string;
  stores: string[];
  metrics: RecallMetric[];
  workflow: WorkflowStep[];
  inventory: InventoryRow[];
  tasks: StaffTask[];
  evidence: EvidenceItem[];
  agents: AgentActivity[];
  insights: MemoryInsight[];
  milestones: Milestone[];
}

export interface WorkflowStep {
  id: string;
  title: string;
  detail: string;
  time: string;
  status: WorkflowStatus;
}

export interface InventoryRow {
  id: string;
  store: string;
  sku: string;
  product: string;
  lot: string;
  onHand: number;
  quarantined: number;
  confidence: number;
  status: "quarantined" | "review" | "clear";
  location: string;
}

export interface StaffTask {
  id: string;
  title: string;
  store: string;
  priority: Severity;
  assignee: string;
  initials: string;
  due: string;
  status: TaskStatus;
}

export interface EvidenceItem {
  id: string;
  label: string;
  status: EvidenceStatus;
}

export interface EvidencePacket {
  incident_id: string;
  packet_version: string;
  filename: string;
  generated_at: string;
  sections: EvidencePacketSection[];
  markdown: string;
}

export interface EvidencePacketSection {
  title: string;
  body: string;
}

export type ReviewStatus = "pending" | "needs-changes" | "approved";

export type ReviewDecision = Exclude<ReviewStatus, "pending">;

export type ReviewChecklistStatus = "passed" | "attention" | "blocked";

export interface ReviewChecklistItem {
  id: string;
  label: string;
  status: ReviewChecklistStatus;
  detail: string;
}

export interface ReviewTimelineEvent {
  id: string;
  title: string;
  detail: string;
  actor: string;
  at: string;
  status: ReviewStatus | ReviewChecklistStatus;
}

export interface EvidenceReviewState {
  incident_id: string;
  packet_filename: string;
  status: ReviewStatus;
  reviewer: string;
  ready_to_submit: boolean;
  blocker_count: number;
  next_action: string;
  checklist: ReviewChecklistItem[];
  timeline: ReviewTimelineEvent[];
}

export interface AgentActivity {
  id: string;
  name: string;
  status: "active" | "waiting" | "complete";
  action: string;
  time: string;
}

export interface MemoryInsight {
  id: string;
  title: string;
  detail: string;
  tone: "success" | "warning" | "neutral";
}

export interface Milestone {
  id: string;
  title: string;
  due: string;
  remaining: string;
  tone: "risk" | "warning" | "neutral";
}
