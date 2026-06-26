import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Bell,
  Brain,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronDown,
  ClipboardCheck,
  ClipboardList,
  Download,
  FileCheck2,
  FileText,
  Filter,
  HelpCircle,
  Mail,
  MoreHorizontal,
  PackageCheck,
  ScanLine,
  Search,
  Settings,
  Shield,
  UserRound,
  Warehouse,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  fetchDashboardSync,
  fetchDemoInspection,
  uploadShelfPhoto,
  type ProviderStatus,
  type ShelfInspectionResult,
} from "./api";
import { demoIncident } from "./data/demoIncident";
import type {
  AgentActivity,
  EvidenceItem,
  EvidenceStatus,
  InventoryRow,
  MemoryInsight,
  Milestone,
  RecallIncident,
  RecallMetric,
  Severity,
  StaffTask,
  TaskStatus,
  WorkflowStatus,
  WorkflowStep,
} from "./types";

const navItems = [
  { label: "Recalls", icon: AlertTriangle },
  { label: "Inventory", icon: Warehouse },
  { label: "Tasks", icon: ClipboardCheck },
  { label: "Evidence", icon: FileText },
  { label: "Memory", icon: Brain },
];

type StoreFilter = "all" | "Store A" | "Store B";
type SyncState = "syncing" | "connected" | "offline";
type InspectionState = "idle" | "loading" | "ready" | "error";

export function App() {
  const [activeNav, setActiveNav] = useState("Recalls");
  const [storeFilter, setStoreFilter] = useState<StoreFilter>("all");
  const [incident, setIncident] = useState<RecallIncident>(demoIncident);
  const [tasks, setTasks] = useState<StaffTask[]>(demoIncident.tasks);
  const [provider, setProvider] = useState<ProviderStatus | null>(null);
  const [syncState, setSyncState] = useState<SyncState>("syncing");
  const [inspection, setInspection] = useState<ShelfInspectionResult | null>(null);
  const [inspectionState, setInspectionState] = useState<InspectionState>("idle");
  const [inspectionError, setInspectionError] = useState("");

  useEffect(() => {
    let active = true;

    fetchDashboardSync()
      .then((sync) => {
        if (!active) {
          return;
        }
        setIncident(sync.incident);
        setTasks(sync.incident.tasks);
        setProvider(sync.provider);
        setSyncState("connected");
        void loadDemoInspection();
      })
      .catch(() => {
        if (active) {
          setSyncState("offline");
        }
      });

    return () => {
      active = false;
    };
  }, []);

  const filteredInventory = useMemo(() => {
    if (storeFilter === "all") {
      return incident.inventory;
    }

    return incident.inventory.filter((row) => row.store === storeFilter);
  }, [incident.inventory, storeFilter]);

  const openTaskCount = tasks.filter((task) => task.status !== "complete").length;
  const evidenceProgress = getEvidenceProgress(incident.evidence);
  const quarantinedTotal = filteredInventory.reduce(
    (total, row) => total + row.quarantined,
    0,
  );

  function toggleTask(taskId: string) {
    setTasks((currentTasks) =>
      currentTasks.map((task) =>
        task.id === taskId
          ? {
              ...task,
              status: task.status === "complete" ? "in-progress" : "complete",
            }
          : task,
      ),
    );
  }

  async function loadDemoInspection() {
    setInspectionState("loading");
    setInspectionError("");
    try {
      const result = await fetchDemoInspection();
      setInspection(result);
      setInspectionState("ready");
    } catch {
      setInspectionState("error");
      setInspectionError("Inspection service is unavailable.");
    }
  }

  async function inspectShelfPhoto(file: File) {
    setInspectionState("loading");
    setInspectionError("");
    try {
      const result = await uploadShelfPhoto(file);
      setInspection(result);
      setInspectionState("ready");
    } catch {
      setInspectionState("error");
      setInspectionError("Upload failed. Use a JPEG, PNG, or WebP image under 8 MB.");
    }
  }

  return (
    <div className="app-shell">
      <Sidebar
        activeNav={activeNav}
        openTaskCount={openTaskCount}
        onSelect={setActiveNav}
      />
      <div className="workspace">
        <TopBar incident={incident} provider={provider} syncState={syncState} />
        <main className="dashboard" aria-label="Recall command center">
          <section className="dashboard-grid">
            <IncidentSummary incident={incident} />
            <aside className="right-rail" aria-label="Live intelligence panels">
              <AgentPanel agents={incident.agents} />
              <MemoryPanel insights={incident.insights} />
            </aside>
            <WorkflowTimeline workflow={incident.workflow} />
            <AffectedInventory
              inventory={filteredInventory}
              storeFilter={storeFilter}
              quarantinedTotal={quarantinedTotal}
              onFilterChange={setStoreFilter}
            />
          </section>
          <section className="lower-grid" aria-label="Recall operations progress">
            <TaskBoard tasks={tasks} onToggleTask={toggleTask} />
            <EvidenceProgress
              evidence={incident.evidence}
              progress={evidenceProgress}
            />
            <ShelfInspectionPanel
              inspection={inspection}
              state={inspectionState}
              error={inspectionError}
              onDemo={loadDemoInspection}
              onUpload={inspectShelfPhoto}
            />
            <Milestones milestones={incident.milestones} />
          </section>
          <MobileInspection incident={incident} />
        </main>
      </div>
    </div>
  );
}

interface ShelfInspectionPanelProps {
  inspection: ShelfInspectionResult | null;
  state: InspectionState;
  error: string;
  onDemo: () => void;
  onUpload: (file: File) => void;
}

function ShelfInspectionPanel({
  inspection,
  state,
  error,
  onDemo,
  onUpload,
}: ShelfInspectionPanelProps) {
  return (
    <section className="panel inspection-panel" aria-labelledby="inspection-title">
      <div className="panel-header with-actions">
        <h2 id="inspection-title">Shelf Inspection</h2>
        <button type="button" className="utility-button" onClick={onDemo}>
          <ScanLine size={16} />
          Demo scan
        </button>
      </div>

      <div className="inspection-body">
        <label className="upload-drop">
          <ScanLine size={24} aria-hidden="true" />
          <span>Upload shelf photo</span>
          <small>JPEG, PNG, or WebP under 8 MB</small>
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={(event) => {
              const file = event.currentTarget.files?.[0];
              if (file) {
                onUpload(file);
              }
              event.currentTarget.value = "";
            }}
          />
        </label>

        <div className={`inspection-result ${state}`}>
          {state === "loading" ? (
            <p>Inspecting label evidence...</p>
          ) : state === "error" ? (
            <p>{error}</p>
          ) : inspection ? (
            <>
              <div className="inspection-result-header">
                <strong>
                  {inspection.recall_match ? "Recall match" : "Review needed"}
                </strong>
                <span>{inspection.extracted.confidence}% confidence</span>
              </div>
              <dl>
                <div>
                  <dt>Product</dt>
                  <dd>{inspection.extracted.product_name}</dd>
                </div>
                <div>
                  <dt>Lot</dt>
                  <dd>{inspection.extracted.lot_code}</dd>
                </div>
                <div>
                  <dt>UPC</dt>
                  <dd>{inspection.extracted.upc}</dd>
                </div>
              </dl>
              <p>{inspection.recommended_action}</p>
              <small>
                {inspection.used_fallback ? "Demo fallback" : "Qwen vision"} ·{" "}
                {inspection.upload.original_filename}
              </small>
            </>
          ) : (
            <p>No shelf image inspected yet.</p>
          )}
        </div>
      </div>
    </section>
  );
}

interface SidebarProps {
  activeNav: string;
  openTaskCount: number;
  onSelect: (label: string) => void;
}

function Sidebar({ activeNav, openTaskCount, onSelect }: SidebarProps) {
  return (
    <aside className="sidebar" aria-label="Primary navigation">
      <div className="brand">
        <div className="brand-mark" aria-hidden="true">
          <PackageCheck size={26} />
        </div>
        <span>BatchHelm AI</span>
      </div>

      <nav className="nav-list" aria-label="BatchHelm sections">
        {navItems.map((item) => {
          const Icon = item.icon;
          const selected = activeNav === item.label;
          return (
            <button
              key={item.label}
              type="button"
              className={`nav-item ${selected ? "selected" : ""}`}
              aria-pressed={selected}
              onClick={() => onSelect(item.label)}
            >
              <Icon size={21} />
              <span>{item.label}</span>
              {item.label === "Tasks" ? (
                <span className="nav-badge">{openTaskCount}</span>
              ) : null}
            </button>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <div className="system-card">
          <span className="system-dot" aria-hidden="true" />
          <div>
            <strong>System Status</strong>
            <span>All systems operational</span>
          </div>
        </div>
        <button type="button" className="footer-link">
          <HelpCircle size={20} />
          <span>Help & Support</span>
        </button>
        <button type="button" className="footer-link">
          <Settings size={20} />
          <span>Settings</span>
        </button>
      </div>
    </aside>
  );
}

function TopBar({
  incident,
  provider,
  syncState,
}: {
  incident: RecallIncident;
  provider: ProviderStatus | null;
  syncState: SyncState;
}) {
  return (
    <header className="topbar">
      <label className="search-box">
        <Search size={18} aria-hidden="true" />
        <span className="sr-only">Search recalls, lots, stores, tasks, evidence</span>
        <input
          type="search"
          placeholder="Search recalls, lots, stores, tasks, evidence..."
        />
        <kbd>⌘K</kbd>
      </label>

      <div className="topbar-actions">
        <div className={`provider-chip ${syncState}`}>
          <span>{syncLabel(syncState)}</span>
          <strong>{provider ? provider.mode : "local demo"}</strong>
        </div>
        <div className="incident-status">
          <span>Incident Status</span>
          <strong>{incident.status.toUpperCase()}</strong>
        </div>
        <button type="button" className="icon-button" aria-label="Notifications">
          <Bell size={20} />
        </button>
        <button type="button" className="profile-button" aria-label="User profile">
          <span className="avatar">OM</span>
          <span className="profile-copy">
            <strong>Operations Manager</strong>
            <span>Central Foods Co.</span>
          </span>
          <ChevronDown size={16} />
        </button>
      </div>
    </header>
  );
}

function IncidentSummary({ incident }: { incident: RecallIncident }) {
  return (
    <section className="incident-card" aria-labelledby="incident-title">
      <div className="incident-alert">
        <AlertTriangle size={18} />
        <span>{incident.title.toUpperCase()}</span>
      </div>

      <div className="incident-main">
        <div className="incident-heading">
          <h1 id="incident-title">{incident.product}</h1>
          <p>
            Lot: <strong>{incident.lotRange}</strong>
          </p>
        </div>

        <div className="metrics-grid" aria-label="Recall metrics">
          {incident.metrics.map((metric) => (
            <Metric key={metric.label} metric={metric} />
          ))}
        </div>
      </div>

      <div className="action-row" aria-label="Recall actions">
        <button type="button" className="action-button active">
          <Shield size={18} />
          <span>Command Center</span>
        </button>
        <button type="button" className="action-button">
          <PackageCheck size={18} />
          <span>Quarantine</span>
          <em>In Progress</em>
        </button>
        <button type="button" className="action-button">
          <Mail size={18} />
          <span>Customer Notice</span>
          <em>Draft</em>
        </button>
        <button type="button" className="action-button">
          <FileCheck2 size={18} />
          <span>Compliance Packet</span>
          <em>In Progress</em>
        </button>
        <button type="button" className="square-button" aria-label="More actions">
          <MoreHorizontal size={18} />
        </button>
      </div>
    </section>
  );
}

function Metric({ metric }: { metric: RecallMetric }) {
  return (
    <div className="metric">
      <span>{metric.label}</span>
      <strong className={metric.tone ? `tone-${metric.tone}` : undefined}>
        {metric.value}
      </strong>
      <small>{metric.detail}</small>
      {metric.label === "Evidence Progress" ? (
        <div className="mini-progress" aria-hidden="true">
          <span style={{ width: metric.value }} />
        </div>
      ) : null}
    </div>
  );
}

function WorkflowTimeline({ workflow }: { workflow: WorkflowStep[] }) {
  return (
    <section className="panel timeline-panel" aria-labelledby="timeline-title">
      <PanelHeader title="Agent Workflow Timeline" />
      <div className="timeline" id="timeline-title">
        {workflow.map((step) => (
          <div className="timeline-item" key={step.id}>
            <span className={`timeline-dot ${step.status}`} aria-hidden="true">
              {step.status === "complete" ? <Check size={13} /> : null}
            </span>
            <div className="timeline-copy">
              <strong>{step.title}</strong>
              <span>{step.detail}</span>
            </div>
            <time>{step.time}</time>
            {step.status === "complete" ? (
              <Check className="row-check" size={16} aria-hidden="true" />
            ) : null}
          </div>
        ))}
      </div>
      <button type="button" className="inline-link">
        View full timeline
        <ArrowRight size={15} />
      </button>
    </section>
  );
}

interface AffectedInventoryProps {
  inventory: InventoryRow[];
  storeFilter: StoreFilter;
  quarantinedTotal: number;
  onFilterChange: (store: StoreFilter) => void;
}

function AffectedInventory({
  inventory,
  storeFilter,
  quarantinedTotal,
  onFilterChange,
}: AffectedInventoryProps) {
  const filterOptions: StoreFilter[] = ["all", "Store A", "Store B"];
  const onHandTotal = inventory.reduce((total, row) => total + row.onHand, 0);

  return (
    <section className="panel inventory-panel" aria-labelledby="inventory-title">
      <div className="panel-header with-actions">
        <h2 id="inventory-title">Affected Inventory</h2>
        <div className="table-actions">
          <div className="segmented" aria-label="Filter inventory by store">
            {filterOptions.map((option) => (
              <button
                key={option}
                type="button"
                className={storeFilter === option ? "selected" : ""}
                onClick={() => onFilterChange(option)}
              >
                {option === "all" ? "All" : option}
              </button>
            ))}
          </div>
          <button type="button" className="utility-button">
            <Filter size={16} />
            Filter
          </button>
          <button type="button" className="utility-button">
            <Download size={16} />
            Export
          </button>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Store</th>
              <th scope="col">SKU</th>
              <th scope="col">Product</th>
              <th scope="col">Lot</th>
              <th scope="col">On Hand</th>
              <th scope="col">Quarantined</th>
              <th scope="col">Confidence</th>
              <th scope="col">Status</th>
              <th scope="col">Location</th>
            </tr>
          </thead>
          <tbody>
            {inventory.map((row) => (
              <tr key={row.id}>
                <td>{row.store}</td>
                <td>{row.sku}</td>
                <td>{row.product}</td>
                <td>{row.lot}</td>
                <td>{row.onHand}</td>
                <td>{row.quarantined}</td>
                <td>
                  <span className="confidence">{row.confidence}%</span>
                </td>
                <td>
                  <StatusPill status={row.status} />
                </td>
                <td>{row.location}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={4}>Showing {inventory.length} items</td>
              <td>{onHandTotal}</td>
              <td>{quarantinedTotal}</td>
              <td colSpan={3} />
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}

function AgentPanel({ agents }: { agents: AgentActivity[] }) {
  return (
    <section className="panel rail-panel" aria-labelledby="agents-title">
      <PanelHeader title="Live Agent Activity" actionLabel="View all" />
      <div className="rail-list" id="agents-title">
        {agents.map((agent, index) => (
          <div className="rail-row" key={agent.id}>
            <span className="agent-icon" aria-hidden="true">
              {index % 3 === 0 ? (
                <PackageCheck size={18} />
              ) : index % 3 === 1 ? (
                <Mail size={18} />
              ) : (
                <FileCheck2 size={18} />
              )}
            </span>
            <div className="rail-copy">
              <div>
                <strong>{agent.name}</strong>
                <span className={`state-pill ${agent.status}`}>{agent.status}</span>
              </div>
              <p>{agent.action}</p>
            </div>
            <time>{agent.time}</time>
          </div>
        ))}
      </div>
    </section>
  );
}

function MemoryPanel({ insights }: { insights: MemoryInsight[] }) {
  return (
    <section className="panel rail-panel" aria-labelledby="memory-title">
      <PanelHeader title="Memory Insights" actionLabel="View all" />
      <div className="memory-list" id="memory-title">
        {insights.map((insight, index) => (
          <div className="memory-row" key={insight.id}>
            <span className={`memory-icon ${insight.tone}`} aria-hidden="true">
              {index === 0 ? (
                <Shield size={20} />
              ) : index === 1 ? (
                <FileText size={20} />
              ) : (
                <BarChart3 size={20} />
              )}
            </span>
            <div>
              <strong>{insight.title}</strong>
              <p>{insight.detail}</p>
            </div>
            <button type="button">View</button>
          </div>
        ))}
      </div>
    </section>
  );
}

interface TaskBoardProps {
  tasks: StaffTask[];
  onToggleTask: (taskId: string) => void;
}

function TaskBoard({ tasks, onToggleTask }: TaskBoardProps) {
  const openCount = tasks.filter((task) => task.status !== "complete").length;

  return (
    <section className="panel task-panel" aria-labelledby="tasks-title">
      <div className="panel-header with-actions">
        <h2 id="tasks-title">Staff Task Board ({openCount} Open Tasks)</h2>
        <div className="table-actions">
          <button type="button" className="utility-button">
            <UserRound size={16} />
            Assign to me
          </button>
          <button type="button" className="utility-button">
            Sort: Priority
            <ChevronDown size={15} />
          </button>
        </div>
      </div>

      <div className="table-wrap compact">
        <table>
          <thead>
            <tr>
              <th scope="col">Task</th>
              <th scope="col">Store</th>
              <th scope="col">Priority</th>
              <th scope="col">Assignee</th>
              <th scope="col">Due</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task) => (
              <tr key={task.id} className={task.status === "complete" ? "done" : ""}>
                <td>
                  <label className="task-check">
                    <input
                      type="checkbox"
                      checked={task.status === "complete"}
                      onChange={() => onToggleTask(task.id)}
                    />
                    <span>{task.title}</span>
                  </label>
                </td>
                <td>{task.store}</td>
                <td>
                  <SeverityPill severity={task.priority} />
                </td>
                <td>
                  <span className="assignee">
                    <span>{task.initials}</span>
                    {task.assignee}
                  </span>
                </td>
                <td>{task.due}</td>
                <td>
                  <TaskState status={task.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button type="button" className="inline-link">
        View all tasks
        <ArrowRight size={15} />
      </button>
    </section>
  );
}

function EvidenceProgress({
  evidence,
  progress,
}: {
  evidence: EvidenceItem[];
  progress: number;
}) {
  return (
    <section className="panel evidence-panel" aria-labelledby="evidence-title">
      <PanelHeader title="Evidence Packet Progress" />
      <div className="evidence-layout" id="evidence-title">
        <div
          className="progress-ring"
          style={{ "--progress": `${progress}%` } as React.CSSProperties}
          aria-label={`Evidence packet ${progress}% complete`}
        >
          <strong>{progress}%</strong>
          <span>Complete</span>
        </div>
        <div className="evidence-list">
          {evidence.map((item) => (
            <div className="evidence-row" key={item.id}>
              <span className={`evidence-dot ${item.status}`} aria-hidden="true">
                {item.status === "completed" ? <Check size={13} /> : null}
              </span>
              <span>{item.label}</span>
              <em>{formatEvidenceStatus(item.status)}</em>
            </div>
          ))}
        </div>
      </div>
      <button type="button" className="inline-link">
        View packet
        <ArrowRight size={15} />
      </button>
    </section>
  );
}

function Milestones({ milestones }: { milestones: Milestone[] }) {
  return (
    <section className="panel milestone-panel" aria-labelledby="milestones-title">
      <PanelHeader title="Next Milestones" />
      <div className="milestone-list" id="milestones-title">
        {milestones.map((milestone) => (
          <div className="milestone-row" key={milestone.id}>
            <CalendarDays size={24} />
            <div>
              <strong>{milestone.title}</strong>
              <span>{milestone.due}</span>
            </div>
            <em className={`timer ${milestone.tone}`}>{milestone.remaining}</em>
          </div>
        ))}
      </div>
      <button type="button" className="inline-link">
        View timeline
        <ArrowRight size={15} />
      </button>
    </section>
  );
}

function MobileInspection({ incident }: { incident: RecallIncident }) {
  return (
    <section className="mobile-inspection" aria-labelledby="mobile-title">
      <div>
        <span className="scan-icon" aria-hidden="true">
          <Activity size={22} />
        </span>
        <div>
          <h2 id="mobile-title">Shelf inspection ready</h2>
          <p>
            Scan {incident.product} lot labels in-store and route uncertain
            matches to review.
          </p>
        </div>
      </div>
      <button type="button">Open scanner</button>
    </section>
  );
}

function PanelHeader({
  title,
  actionLabel,
}: {
  title: string;
  actionLabel?: string;
}) {
  return (
    <div className="panel-header">
      <h2>{title}</h2>
      {actionLabel ? (
        <button type="button" className="inline-link">
          {actionLabel}
          <ArrowRight size={15} />
        </button>
      ) : null}
    </div>
  );
}

function StatusPill({ status }: { status: InventoryRow["status"] }) {
  return (
    <span className={`status-pill ${status}`}>
      {status === "quarantined" ? <Shield size={13} /> : null}
      {status}
    </span>
  );
}

function SeverityPill({ severity }: { severity: Severity }) {
  return <span className={`severity-pill ${severity}`}>{severity}</span>;
}

function TaskState({ status }: { status: TaskStatus }) {
  return (
    <span className={`task-state ${status}`}>
      {status === "complete" ? <CheckCircle2 size={13} /> : null}
      {formatTaskStatus(status)}
    </span>
  );
}

function getEvidenceProgress(evidence: EvidenceItem[]) {
  const score = evidence.reduce((total, item) => {
    if (item.status === "completed") {
      return total + 1;
    }
    if (item.status === "in-progress") {
      return total + 0.42;
    }
    return total;
  }, 0);

  return Math.round((score / evidence.length) * 100);
}

function formatTaskStatus(status: TaskStatus) {
  const labels: Record<TaskStatus, string> = {
    "not-started": "Not Started",
    "in-progress": "In Progress",
    blocked: "Blocked",
    complete: "Complete",
  };

  return labels[status];
}

function formatEvidenceStatus(status: EvidenceStatus) {
  const labels: Record<EvidenceStatus, string> = {
    completed: "Completed",
    "in-progress": "In Progress",
    pending: "Pending",
  };

  return labels[status];
}

function syncLabel(syncState: SyncState) {
  const labels: Record<SyncState, string> = {
    syncing: "Syncing API",
    connected: "API Connected",
    offline: "Local Demo",
  };

  return labels[syncState];
}
