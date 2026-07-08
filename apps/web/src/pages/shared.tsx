import type { RecallIncident, RecallMetric, AgentActivity, MemoryInsight, Milestone, WorkflowStep } from "../types";

// Re-export shared helper components used across pages

export function Metric({ metric }: { metric: RecallMetric }) {
  return (
    <div className="metric">
      <span>{metric.label}</span>
      <strong className={metric.tone ? `tone-${metric.tone}` : undefined}>
        {metric.value}
      </strong>
      <small>{metric.detail}</small>
      {metric.label === "Evidence Progress" ? (
        <div className="mini-progress" aria-hidden="true">
          <span style={{ width: metric.value } as React.CSSProperties} />
        </div>
      ) : null}
    </div>
  );
}

export function StatusPill({ status }: { status: "quarantined" | "review" | "clear" }) {
  return (
    <span className={`status-pill ${status}`}>
      {status}
    </span>
  );
}

export function SeverityPill({ severity }: { severity: "low" | "medium" | "high" | "critical" }) {
  return <span className={`severity-pill ${severity}`}>{severity}</span>;
}

export function TaskState({ status }: { status: "not-started" | "in-progress" | "blocked" | "complete" }) {
  const labels: Record<typeof status, string> = {
    "not-started": "Not Started",
    "in-progress": "In Progress",
    blocked: "Blocked",
    complete: "Complete",
  };
  return (
    <span className={`task-state ${status}`}>
      {labels[status]}
    </span>
  );
}

export function PanelHeader({
  title,
  subtitle,
  actionLabel,
  onAction,
}: {
  title: string;
  subtitle?: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="panel-header">
      <div>
        <h2>{title}</h2>
        {subtitle ? <p className="panel-header-subtitle">{subtitle}</p> : null}
      </div>
      {actionLabel ? (
        <button type="button" className="inline-link" onClick={onAction}>
          {actionLabel}
          <span>→</span>
        </button>
      ) : null}
    </div>
  );
}

export function getEvidenceProgress(evidence: { status: "completed" | "in-progress" | "pending" }[]) {
  const score = evidence.reduce((total, item) => {
    if (item.status === "completed") return total + 1;
    if (item.status === "in-progress") return total + 0.42;
    return total;
  }, 0);
  return Math.round((score / evidence.length) * 100);
}

export function formatTaskStatus(status: "not-started" | "in-progress" | "blocked" | "complete") {
  const labels: Record<typeof status, string> = {
    "not-started": "Not Started",
    "in-progress": "In Progress",
    blocked: "Blocked",
    complete: "Complete",
  };
  return labels[status];
}

export function formatEvidenceStatus(status: "completed" | "in-progress" | "pending") {
  const labels: Record<typeof status, string> = {
    completed: "Completed",
    "in-progress": "In Progress",
    pending: "Pending",
  };
  return labels[status];
}

export function compactSectionBody(body: string) {
  return body
    .split("\n")
    .filter((line) => line.trim() && !line.startsWith("| ---"))
    .slice(0, 2)
    .map((line) => line.replace(/^\| /, "").replace(/ \|$/g, "").replace(/ \| /g, " / "))
    .join(" ");
}

export function formatPacketTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function csvCell(value: string) {
  return /[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}
