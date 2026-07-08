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
  FilePlus2,
  FileText,
  Filter,
  HelpCircle,
  Mail,
  MoreHorizontal,
  PackageCheck,
  Printer,
  ScanLine,
  Search,
  Settings,
  Shield,
  UserRound,
  Warehouse,
} from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import {
  evidencePacketDownloadUrl,
  fetchDashboardSync,
  fetchDemoInspection,
  fetchEvidencePacket,
  fetchEvidenceReview,
  submitReviewDecision,
  toIncident,
  uploadShelfPhoto,
  type ProviderProofState,
  type ProviderStatus,
  type QwenVerificationReceipt,
  type ShelfInspectionResult,
} from "./api";
import { demoIncident } from "./data/demoIncident";
import { EvidenceReviewGate } from "./EvidenceReviewGate";
import { IntakeWorkspace } from "./IntakeWorkspace";
import { MissionControl } from "./MissionControl";
import {
  ProviderEvidenceControl,
  type ProviderEvidenceState,
} from "./ProviderEvidenceControl";
import { useIntakeWorkspace } from "./useIntakeWorkspace";
import { useOrchestrationRun } from "./useOrchestrationRun";
import type {
  AgentActivity,
  EvidenceItem,
  EvidencePacket,
  EvidenceReviewState,
  EvidenceStatus,
  InventoryRow,
  MemoryInsight,
  Milestone,
  RecallIncident,
  RecallMetric,
  ReviewDecision,
  Severity,
  StaffTask,
  TaskStatus,
  WorkflowStatus,
  WorkflowStep,
} from "./types";

const navItems = [
  { label: "Recalls", icon: AlertTriangle, section: "section-recalls" },
  { label: "Inventory", icon: Warehouse, section: "section-inventory" },
  { label: "Tasks", icon: ClipboardCheck, section: "section-tasks" },
  { label: "Evidence", icon: FileText, section: "section-evidence" },
  { label: "Memory", icon: Brain, section: "section-memory" },
];

const helpUrl = "https://github.com/ankitranjan-dsai/batchhelm-ai#readme";

type StoreFilter = "all" | "Store A" | "Store B";
type StatusFilter = "all" | InventoryRow["status"];
type EvidenceView = "review" | "packet";
type InspectionState = "idle" | "loading" | "ready" | "error";
type PacketState = "idle" | "loading" | "ready" | "error";

function scrollToSection(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function App() {
  const orchestrationController = useOrchestrationRun();
  const { session: orchestration, rerun: rerunOrchestration } =
    orchestrationController;
  const intakeController = useIntakeWorkspace({
    onRunAccepted: orchestrationController.adoptRun,
  });
  const [activeNav, setActiveNav] = useState("Recalls");
  const [searchQuery, setSearchQuery] = useState("");
  const [storeFilter, setStoreFilter] = useState<StoreFilter>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [evidenceView, setEvidenceView] = useState<EvidenceView>("review");
  const [incident, setIncident] = useState<RecallIncident>(demoIncident);
  const [tasks, setTasks] = useState<StaffTask[]>(demoIncident.tasks);
  const shelfInputRef = useRef<HTMLInputElement>(null);
  const [provider, setProvider] = useState<ProviderStatus | null>(null);
  const [providerProof, setProviderProof] =
    useState<QwenVerificationReceipt | null>(null);
  const [providerEvidenceState, setProviderEvidenceState] =
    useState<ProviderEvidenceState>("loading");
  const [inspection, setInspection] = useState<ShelfInspectionResult | null>(null);
  const [inspectionState, setInspectionState] = useState<InspectionState>("idle");
  const [inspectionError, setInspectionError] = useState("");
  const [packet, setPacket] = useState<EvidencePacket | null>(null);
  const [packetState, setPacketState] = useState<PacketState>("idle");
  const [packetError, setPacketError] = useState("");
  const [review, setReview] = useState<EvidenceReviewState | null>(null);
  const [reviewState, setReviewState] = useState<PacketState>("idle");
  const [reviewError, setReviewError] = useState("");

  useEffect(() => {
    let active = true;

    void loadDemoInspection();
    void loadEvidenceWorkspace();

    fetchDashboardSync()
      .then((sync) => {
        if (!active) {
          return;
        }
        setProvider(sync.provider);
        setProviderProof(sync.proof);
        setProviderEvidenceState(sync.proofState);
      })
      .catch(() => {
        if (active) {
          setProviderEvidenceState("unavailable");
        }
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (orchestration.result) {
      const nextIncident = toIncident(orchestration.result.analysis);
      setIncident(nextIncident);
      setTasks(nextIncident.tasks);
    }
  }, [orchestration.result]);

  const filteredInventory = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return incident.inventory.filter((row) => {
      if (storeFilter !== "all" && row.store !== storeFilter) {
        return false;
      }
      if (statusFilter !== "all" && row.status !== statusFilter) {
        return false;
      }
      if (!query) {
        return true;
      }
      return [row.store, row.sku, row.product, row.lot, row.location, row.status].some(
        (value) => value.toLowerCase().includes(query),
      );
    });
  }, [incident.inventory, storeFilter, statusFilter, searchQuery]);

  const visibleTasks = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) {
      return tasks;
    }
    return tasks.filter((task) =>
      [task.title, task.store, task.assignee, task.priority, task.status].some(
        (value) => value.toLowerCase().includes(query),
      ),
    );
  }, [tasks, searchQuery]);

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

  function assignOpenTasksToMe() {
    setTasks((currentTasks) =>
      currentTasks.map((task) =>
        task.status === "complete"
          ? task
          : { ...task, assignee: "Operations Manager", initials: "OM" },
      ),
    );
  }

  function handleNavSelect(label: string) {
    setActiveNav(label);
    const section = navItems.find((item) => item.label === label)?.section;
    if (section) {
      scrollToSection(section);
    }
  }

  function openEvidenceView(view: EvidenceView) {
    setEvidenceView(view);
    scrollToSection("section-evidence");
  }

  function openScanner() {
    scrollToSection("section-inspection");
    shelfInputRef.current?.click();
  }

  function exportInventoryCsv() {
    const header = [
      "Store",
      "SKU",
      "Product",
      "Lot",
      "On Hand",
      "Quarantined",
      "Confidence",
      "Status",
      "Location",
    ];
    const rows = filteredInventory.map((row) => [
      row.store,
      row.sku,
      row.product,
      row.lot,
      String(row.onHand),
      String(row.quarantined),
      `${row.confidence}%`,
      row.status,
      row.location,
    ]);
    const csv = [header, ...rows]
      .map((line) => line.map(csvCell).join(","))
      .join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `batchhelm-inventory-${incident.id}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function loadDemoInspection() {
    setInspectionState("loading");
    setInspectionError("");
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const result = await fetchDemoInspection(controller.signal);
      setInspection(result);
      setInspectionState("ready");
    } catch {
      setInspectionState("error");
      setInspectionError("Inspection service is unavailable or timed out.");
    } finally {
      clearTimeout(timeout);
    }
  }

  async function inspectShelfPhoto(file: File) {
    setInspectionState("loading");
    setInspectionError("");
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30000);
    try {
      const result = await uploadShelfPhoto(file, controller.signal);
      setInspection(result);
      setInspectionState("ready");
    } catch {
      setInspectionState("error");
      setInspectionError("Upload failed or timed out. Use a JPEG, PNG, or WebP image under 8 MB.");
    } finally {
      clearTimeout(timeout);
    }
  }

  async function loadEvidencePacket() {
    setPacketState("loading");
    setPacketError("");
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const result = await fetchEvidencePacket(controller.signal);
      setPacket(result);
      setPacketState("ready");
    } catch {
      setPacketState("error");
      setPacketError("Evidence packet service is unavailable or timed out.");
    } finally {
      clearTimeout(timeout);
    }
  }

  async function loadEvidenceReview() {
    setReviewState("loading");
    setReviewError("");
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const result = await fetchEvidenceReview(controller.signal);
      setReview(result);
      setReviewState("ready");
    } catch {
      setReviewState("error");
      setReviewError("Evidence review service is unavailable or timed out.");
    } finally {
      clearTimeout(timeout);
    }
  }

  async function loadEvidenceWorkspace() {
    await Promise.all([loadEvidencePacket(), loadEvidenceReview()]);
  }

  async function handleReviewDecision(decision: ReviewDecision) {
    setReviewState("loading");
    setReviewError("");
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const result = await submitReviewDecision(decision, controller.signal);
      setReview(result);
      setReviewState("ready");
    } catch {
      setReviewState("error");
      setReviewError("Review decision could not be applied or timed out.");
    } finally {
      clearTimeout(timeout);
    }
  }

  return (
    <>
      <a href="#section-recalls" className="skip-link">
        Skip to main content
      </a>
      <div className="app-shell">
        <Sidebar
          activeNav={activeNav}
          openTaskCount={openTaskCount}
          onSelect={handleNavSelect}
        />
        <div className="workspace">
          <TopBar
            incident={incident}
            provider={provider}
            providerProof={providerProof}
            providerEvidenceState={providerEvidenceState}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            openTaskCount={openTaskCount}
            evidenceProgress={evidenceProgress}
          />
          <main className="dashboard" aria-label="Recall command center">
            <section className="dashboard-grid">
              <IncidentSummary
                incident={incident}
                onNewRecall={intakeController.open}
                onQuarantine={() => scrollToSection("section-inventory")}
                onCustomerNotice={() => openEvidenceView("review")}
                onCompliancePacket={() => openEvidenceView("packet")}
              />
              <aside className="right-rail" aria-label="Live intelligence panels">
                <AgentPanel agents={incident.agents} />
                <MemoryPanel insights={incident.insights} />
              </aside>
              <WorkflowTimeline
                workflow={incident.workflow}
                onViewFull={() => scrollToSection("section-mission")}
              />
              <AffectedInventory
                incident={incident}
                inventory={filteredInventory}
                storeFilter={storeFilter}
                statusFilter={statusFilter}
                quarantinedTotal={quarantinedTotal}
                onFilterChange={setStoreFilter}
                onStatusFilterChange={setStatusFilter}
                onExport={exportInventoryCsv}
              />
            </section>
            <section aria-label="Agent mission control" id="section-mission">
              <MissionControl
                session={orchestration}
                onRerun={rerunOrchestration}
              />
            </section>
            <section className="lower-grid" aria-label="Recall operations progress">
              <TaskBoard
                tasks={visibleTasks}
                onToggleTask={toggleTask}
                onAssignToMe={assignOpenTasksToMe}
              />
              <EvidenceProgress
                evidence={incident.evidence}
                progress={evidenceProgress}
                packet={packet}
                packetState={packetState}
                packetError={packetError}
                review={review}
                reviewState={reviewState}
                reviewError={reviewError}
                activeView={evidenceView}
                onViewChange={setEvidenceView}
                onRefresh={loadEvidenceWorkspace}
                onReviewDecision={handleReviewDecision}
              />
              <ShelfInspectionPanel
                inspection={inspection}
                state={inspectionState}
                error={inspectionError}
                inputRef={shelfInputRef}
                onDemo={loadDemoInspection}
                onUpload={inspectShelfPhoto}
              />
              <Milestones
                milestones={incident.milestones}
                onViewTimeline={() => scrollToSection("section-timeline")}
              />
            </section>
            <MobileInspection incident={incident} onOpenScanner={openScanner} />
          </main>
        </div>
        <IntakeWorkspace controller={intakeController} />
      </div>
    </>
  );
}

interface ShelfInspectionPanelProps {
  inspection: ShelfInspectionResult | null;
  state: InspectionState;
  error: string;
  inputRef: React.Ref<HTMLInputElement>;
  onDemo: () => void;
  onUpload: (file: File) => void;
}

function ShelfInspectionPanel({
  inspection,
  state,
  error,
  inputRef,
  onDemo,
  onUpload,
}: ShelfInspectionPanelProps) {
  return (
    <section
      className="panel inspection-panel"
      aria-labelledby="inspection-title"
      id="section-inspection"
    >
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
            ref={inputRef}
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
        <a
          className="footer-link"
          href={helpUrl}
          target="_blank"
          rel="noreferrer"
        >
          <HelpCircle size={20} />
          <span>Help & Support</span>
        </a>
        <button
          type="button"
          className="footer-link"
          disabled
          title="Settings are managed by your workspace admin in this pilot"
        >
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
  providerProof,
  providerEvidenceState,
  searchQuery,
  onSearchChange,
  openTaskCount,
  evidenceProgress,
}: {
  incident: RecallIncident;
  provider: ProviderStatus | null;
  providerProof: QwenVerificationReceipt | null;
  providerEvidenceState: "loading" | ProviderProofState;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  openTaskCount: number;
  evidenceProgress: number;
}) {
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function focusSearch(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
      }
    }
    window.addEventListener("keydown", focusSearch);
    return () => window.removeEventListener("keydown", focusSearch);
  }, []);

  return (
    <header className="topbar">
      <label className="search-box">
        <Search size={18} aria-hidden="true" />
        <span className="sr-only">Search recalls, lots, stores, tasks, evidence</span>
        <input
          type="search"
          placeholder="Search recalls, lots, stores, tasks, evidence..."
          ref={searchRef}
          value={searchQuery}
          onChange={(event) => onSearchChange(event.currentTarget.value)}
        />
        <kbd>⌘K</kbd>
      </label>

      <div className="topbar-actions">
        <ProviderEvidenceControl
          provider={provider}
          proof={providerProof}
          state={providerEvidenceState}
        />
        <div className="incident-status">
          <span>Incident Status</span>
          <strong>{incident.status.toUpperCase()}</strong>
        </div>
        <Dropdown
          label="Notifications"
          renderTrigger={(props) => (
            <button
              type="button"
              className="icon-button"
              aria-label="Notifications"
              {...props}
            >
              <Bell size={20} />
            </button>
          )}
        >
          <div className="dropdown-note">
            {openTaskCount > 0
              ? `${openTaskCount} staff task${openTaskCount === 1 ? "" : "s"} still open.`
              : "All staff tasks are complete."}
          </div>
          <div className="dropdown-note">
            Evidence packet {evidenceProgress}% complete.
          </div>
          <div className="dropdown-note">
            Incident {incident.id} is {incident.status}.
          </div>
        </Dropdown>
        <Dropdown
          label="User profile"
          renderTrigger={(props) => (
            <button
              type="button"
              className="profile-button"
              aria-label="User profile"
              {...props}
            >
              <span className="avatar">OM</span>
              <span className="profile-copy">
                <strong>Operations Manager</strong>
                <span>Central Foods Co.</span>
              </span>
              <ChevronDown size={16} />
            </button>
          )}
        >
          <div className="dropdown-note">
            Signed in as <strong>Operations Manager</strong> — reviewer of record
            for this recall.
          </div>
          <a
            className="dropdown-item"
            href={helpUrl}
            target="_blank"
            rel="noreferrer"
          >
            <HelpCircle size={15} />
            Help & Support
          </a>
        </Dropdown>
      </div>
    </header>
  );
}

function IncidentSummary({
  incident,
  onNewRecall,
  onQuarantine,
  onCustomerNotice,
  onCompliancePacket,
}: {
  incident: RecallIncident;
  onNewRecall: () => void;
  onQuarantine: () => void;
  onCustomerNotice: () => void;
  onCompliancePacket: () => void;
}) {
  return (
    <section
      className="incident-card"
      aria-labelledby="incident-title"
      id="section-recalls"
    >
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
        <button type="button" className="action-button" onClick={onQuarantine}>
          <PackageCheck size={18} />
          <span>Quarantine</span>
          <em>In Progress</em>
        </button>
        <button type="button" className="action-button" onClick={onCustomerNotice}>
          <Mail size={18} />
          <span>Customer Notice</span>
          <em>Draft</em>
        </button>
        <button type="button" className="action-button" onClick={onCompliancePacket}>
          <FileCheck2 size={18} />
          <span>Compliance Packet</span>
          <em>In Progress</em>
        </button>
        <button
          type="button"
          className="action-button new-recall-button"
          onClick={onNewRecall}
        >
          <FilePlus2 size={18} />
          <span>New recall</span>
        </button>
        <Dropdown
          label="More actions"
          renderTrigger={(props) => (
            <button
              type="button"
              className="square-button"
              aria-label="More actions"
              {...props}
            >
              <MoreHorizontal size={18} />
            </button>
          )}
        >
          <a className="dropdown-item" href={evidencePacketDownloadUrl}>
            <Download size={15} />
            Download evidence packet
          </a>
          <button
            type="button"
            className="dropdown-item"
            onClick={() => window.print()}
          >
            <Printer size={15} />
            Print dashboard summary
          </button>
        </Dropdown>
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

function WorkflowTimeline({
  workflow,
  onViewFull,
}: {
  workflow: WorkflowStep[];
  onViewFull: () => void;
}) {
  return (
    <section
      className="panel timeline-panel"
      aria-labelledby="timeline-title"
      id="section-timeline"
    >
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
      <button type="button" className="inline-link" onClick={onViewFull}>
        View full timeline
        <ArrowRight size={15} />
      </button>
    </section>
  );
}

const statusFilterOptions: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All statuses" },
  { value: "quarantined", label: "Quarantined" },
  { value: "review", label: "Review" },
  { value: "clear", label: "Clear" },
];

interface AffectedInventoryProps {
  incident: RecallIncident;
  inventory: InventoryRow[];
  storeFilter: StoreFilter;
  statusFilter: StatusFilter;
  quarantinedTotal: number;
  onFilterChange: (store: StoreFilter) => void;
  onStatusFilterChange: (status: StatusFilter) => void;
  onExport: () => void;
}

function AffectedInventory({
  incident,
  inventory,
  storeFilter,
  statusFilter,
  quarantinedTotal,
  onFilterChange,
  onStatusFilterChange,
  onExport,
}: AffectedInventoryProps) {
  const filterOptions: StoreFilter[] = ["all", "Store A", "Store B"];
  const onHandTotal = inventory.reduce((total, row) => total + row.onHand, 0);
  const statusLabel = statusFilterOptions.find(
    (option) => option.value === statusFilter,
  )?.label;

  return (
    <section
      className="panel inventory-panel"
      aria-labelledby="inventory-title"
      id="section-inventory"
    >
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
          <Dropdown
            label="Filter inventory by status"
            renderTrigger={(props) => (
              <button type="button" className="utility-button" {...props}>
                <Filter size={16} />
                {statusFilter === "all" ? "Filter" : statusLabel}
              </button>
            )}
          >
            {statusFilterOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                className={`dropdown-item ${
                  statusFilter === option.value ? "selected" : ""
                }`}
                onClick={() => onStatusFilterChange(option.value)}
              >
                {statusFilter === option.value ? <Check size={15} /> : null}
                {option.label}
              </button>
            ))}
          </Dropdown>
          <button type="button" className="utility-button" onClick={onExport}>
            <Download size={16} />
            Export
          </button>
        </div>
      </div>

      <div className="table-wrap">
        <table aria-labelledby="inventory-title">
          <caption className="sr-only">
            Affected inventory for {incident.product} lots {incident.lotRange}
          </caption>
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
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? agents : agents.slice(0, 5);

  return (
    <section className="panel rail-panel" aria-labelledby="agents-title">
      <PanelHeader
        title="Live Agent Activity"
        actionLabel={
          agents.length > 5 ? (expanded ? "Show less" : "View all") : undefined
        }
        onAction={() => setExpanded((current) => !current)}
      />
      <div className="rail-list" id="agents-title">
        {visible.map((agent, index) => (
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
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? insights : insights.slice(0, 3);

  return (
    <section
      className="panel rail-panel"
      aria-labelledby="memory-title"
      id="section-memory"
    >
      <PanelHeader
        title="Memory Insights"
        actionLabel={
          insights.length > 3 ? (expanded ? "Show less" : "View all") : undefined
        }
        onAction={() => setExpanded((current) => !current)}
      />
      <div className="memory-list" id="memory-title">
        {visible.map((insight, index) => (
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
          </div>
        ))}
      </div>
    </section>
  );
}

type TaskSort = "priority" | "due" | "status";

const taskSortLabels: Record<TaskSort, string> = {
  priority: "Priority",
  due: "Due",
  status: "Status",
};

const severityRank: Record<Severity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

const taskStatusRank: Record<TaskStatus, number> = {
  blocked: 0,
  "in-progress": 1,
  "not-started": 2,
  complete: 3,
};

interface TaskBoardProps {
  tasks: StaffTask[];
  onToggleTask: (taskId: string) => void;
  onAssignToMe: () => void;
}

function TaskBoard({ tasks, onToggleTask, onAssignToMe }: TaskBoardProps) {
  const [sort, setSort] = useState<TaskSort>("priority");
  const [expanded, setExpanded] = useState(false);
  const openCount = tasks.filter((task) => task.status !== "complete").length;

  const sortedTasks = useMemo(() => {
    const copy = [...tasks];
    if (sort === "priority") {
      copy.sort((a, b) => severityRank[a.priority] - severityRank[b.priority]);
    } else if (sort === "status") {
      copy.sort((a, b) => taskStatusRank[a.status] - taskStatusRank[b.status]);
    } else {
      copy.sort((a, b) => a.due.localeCompare(b.due));
    }
    return copy;
  }, [tasks, sort]);

  const visibleTasks = expanded ? sortedTasks : sortedTasks.slice(0, 5);

  return (
    <section
      className="panel task-panel"
      aria-labelledby="tasks-title"
      id="section-tasks"
    >
      <div className="panel-header with-actions">
        <h2 id="tasks-title">Staff Task Board ({openCount} Open Tasks)</h2>
        <div className="table-actions">
          <button
            type="button"
            className="utility-button"
            onClick={onAssignToMe}
            disabled={openCount === 0}
          >
            <UserRound size={16} />
            Assign to me
          </button>
          <Dropdown
            label="Sort tasks"
            renderTrigger={(props) => (
              <button type="button" className="utility-button" {...props}>
                Sort: {taskSortLabels[sort]}
                <ChevronDown size={15} />
              </button>
            )}
          >
            {(Object.keys(taskSortLabels) as TaskSort[]).map((option) => (
              <button
                key={option}
                type="button"
                className={`dropdown-item ${sort === option ? "selected" : ""}`}
                onClick={() => setSort(option)}
              >
                {sort === option ? <Check size={15} /> : null}
                {taskSortLabels[option]}
              </button>
            ))}
          </Dropdown>
        </div>
      </div>

      <div className="table-wrap compact">
        <table aria-labelledby="tasks-title">
          <caption className="sr-only">Staff tasks for the active recall</caption>
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
            {visibleTasks.map((task) => (
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
        {tasks.length === 0 ? (
          <p className="empty-note">No staff tasks match the current search.</p>
        ) : null}
      </div>
      {sortedTasks.length > 5 ? (
        <button
          type="button"
          className="inline-link"
          onClick={() => setExpanded((current) => !current)}
        >
          {expanded ? "Show fewer tasks" : `View all tasks (${sortedTasks.length})`}
          <ArrowRight size={15} />
        </button>
      ) : null}
    </section>
  );
}

function EvidenceProgress({
  evidence,
  progress,
  packet,
  packetState,
  packetError,
  review,
  reviewState,
  reviewError,
  activeView,
  onViewChange,
  onRefresh,
  onReviewDecision,
}: {
  evidence: EvidenceItem[];
  progress: number;
  packet: EvidencePacket | null;
  packetState: PacketState;
  packetError: string;
  review: EvidenceReviewState | null;
  reviewState: PacketState;
  reviewError: string;
  activeView: EvidenceView;
  onViewChange: (view: EvidenceView) => void;
  onRefresh: () => void;
  onReviewDecision: (decision: ReviewDecision) => void;
}) {
  const isRefreshing =
    packetState === "loading" || reviewState === "loading";

  return (
    <section
      className="panel evidence-panel"
      aria-labelledby="evidence-title"
      id="section-evidence"
    >
      <div className="panel-header with-actions">
        <h2 id="evidence-title">Evidence Packet Progress</h2>
        <div className="packet-actions">
          <button
            type="button"
            className="utility-button"
            onClick={onRefresh}
            disabled={isRefreshing}
          >
            <FileCheck2 size={16} />
            {isRefreshing ? "Syncing" : "Refresh"}
          </button>
          <a className="utility-button" href={evidencePacketDownloadUrl}>
            <Download size={16} />
            Download .md
          </a>
        </div>
      </div>
      <div className="evidence-view-tabs" role="tablist" aria-label="Evidence views">
        <button
          type="button"
          role="tab"
          aria-selected={activeView === "review"}
          className={activeView === "review" ? "active" : ""}
          onClick={() => onViewChange("review")}
        >
          Review
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeView === "packet"}
          className={activeView === "packet" ? "active" : ""}
          onClick={() => onViewChange("packet")}
        >
          Packet
        </button>
      </div>
      <div className="evidence-view" role="tabpanel">
        {activeView === "review" ? (
          <>
            {reviewError ? <p className="packet-error">{reviewError}</p> : null}
            {review ? (
              <EvidenceReviewGate
                review={review}
                isSubmitting={reviewState === "loading"}
                onDecision={onReviewDecision}
              />
            ) : reviewState === "loading" ? (
              <EvidenceViewLoading label="Loading review controls" />
            ) : null}
          </>
        ) : (
          <>
            {packetError ? <p className="packet-error">{packetError}</p> : null}
            <div className="evidence-layout">
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
                    <span
                      className={`evidence-dot ${item.status}`}
                      aria-hidden="true"
                    >
                      {item.status === "completed" ? <Check size={13} /> : null}
                    </span>
                    <span>{item.label}</span>
                    <em>{formatEvidenceStatus(item.status)}</em>
                  </div>
                ))}
              </div>
            </div>
            {packet ? (
              <EvidencePacketPreview packet={packet} />
            ) : packetState === "loading" ? (
              <EvidenceViewLoading label="Generating packet preview" />
            ) : null}
          </>
        )}
      </div>
    </section>
  );
}

function EvidenceViewLoading({ label }: { label: string }) {
  return (
    <div className="evidence-view-loading" role="status">
      <span aria-hidden="true" />
      {label}
    </div>
  );
}

function EvidencePacketPreview({ packet }: { packet: EvidencePacket }) {
  return (
    <div className="packet-preview" aria-label="Evidence packet preview">
      <div className="packet-preview-header">
        <span className="packet-icon" aria-hidden="true">
          <FileText size={18} />
        </span>
        <div>
          <strong>{packet.filename}</strong>
          <span>Generated {formatPacketTimestamp(packet.generated_at)}</span>
        </div>
      </div>
      <div className="packet-sections">
        {packet.sections.slice(0, 3).map((section) => (
          <article className="packet-section" key={section.title}>
            <strong>{section.title}</strong>
            <p>{compactSectionBody(section.body)}</p>
          </article>
        ))}
      </div>
    </div>
  );
}

function Milestones({
  milestones,
  onViewTimeline,
}: {
  milestones: Milestone[];
  onViewTimeline: () => void;
}) {
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
      <button type="button" className="inline-link" onClick={onViewTimeline}>
        View timeline
        <ArrowRight size={15} />
      </button>
    </section>
  );
}

function MobileInspection({
  incident,
  onOpenScanner,
}: {
  incident: RecallIncident;
  onOpenScanner: () => void;
}) {
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
      <button type="button" onClick={onOpenScanner}>
        Open scanner
      </button>
    </section>
  );
}

function PanelHeader({
  title,
  actionLabel,
  onAction,
}: {
  title: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="panel-header">
      <h2>{title}</h2>
      {actionLabel ? (
        <button type="button" className="inline-link" onClick={onAction}>
          {actionLabel}
          <ArrowRight size={15} />
        </button>
      ) : null}
    </div>
  );
}

function Dropdown({
  label,
  renderTrigger,
  children,
}: {
  label: string;
  renderTrigger: (props: {
    onClick: () => void;
    "aria-haspopup": "menu";
    "aria-expanded": boolean;
  }) => ReactNode;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="dropdown">
      {renderTrigger({
        onClick: () => setOpen((current) => !current),
        "aria-haspopup": "menu",
        "aria-expanded": open,
      })}
      {open ? (
        <>
          <button
            type="button"
            className="dropdown-backdrop"
            aria-label={`Close ${label}`}
            onClick={() => setOpen(false)}
          />
          <div
            className="dropdown-menu"
            role="menu"
            aria-label={label}
            onClickCapture={() => setOpen(false)}
          >
            {children}
          </div>
        </>
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

function csvCell(value: string) {
  return /[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
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

function compactSectionBody(body: string) {
  return body
    .split("\n")
    .filter((line) => line.trim() && !line.startsWith("| ---"))
    .slice(0, 2)
    .map((line) => line.replace(/^\| /, "").replace(/ \|$/g, "").replace(/ \| /g, " / "))
    .join(" ");
}

function formatPacketTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}
