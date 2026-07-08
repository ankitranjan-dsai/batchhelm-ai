import { Routes, Route, Link, useLocation } from "react-router-dom";
import {
  AlertTriangle,
  BarChart3,
  Bell,
  Brain,
  ChevronDown,
  ClipboardCheck,
  FileText,
  HelpCircle,
  PackageCheck,
  Search,
  Settings,
  Warehouse,
} from "lucide-react";
import { Suspense, lazy, useEffect, useState, useRef, useCallback } from "react";
import {
  fetchDashboardSync,
  fetchDemoInspection,
  fetchEvidencePacket,
  fetchEvidenceReview,
  submitReviewDecision,
  uploadShelfPhoto,
  type ProviderProofState,
  type ProviderStatus,
  type QwenVerificationReceipt,
} from "./api";
import { demoIncident } from "./data/demoIncident";
import type { EvidencePacket, EvidenceReviewState, ReviewDecision } from "./types";
import type { ShelfInspectionResult } from "./api";
import { IntakeWorkspace } from "./IntakeWorkspace";
import { ProviderEvidenceControl } from "./ProviderEvidenceControl";
import { useIntakeWorkspace } from "./useIntakeWorkspace";
import { useOrchestrationRun } from "./useOrchestrationRun";

import { Dashboard } from "./pages/Dashboard";

const InventoryPage = lazy(() => import("./pages/InventoryPage").then((m) => ({ default: m.InventoryPage })));
const AgentsPage = lazy(() => import("./pages/AgentsPage").then((m) => ({ default: m.AgentsPage })));
const TasksPage = lazy(() => import("./pages/TasksPage").then((m) => ({ default: m.TasksPage })));
const EvidencePage = lazy(() => import("./pages/EvidencePage").then((m) => ({ default: m.EvidencePage })));
const TimelinePage = lazy(() => import("./pages/TimelinePage").then((m) => ({ default: m.TimelinePage })));
const MemoryPage = lazy(() => import("./pages/MemoryPage").then((m) => ({ default: m.MemoryPage })));
const SettingsPage = lazy(() => import("./pages/SettingsPage").then((m) => ({ default: m.SettingsPage })));
const NotFound = lazy(() => import("./pages/NotFound").then((m) => ({ default: m.NotFound })));

const helpUrl = "https://github.com/ankitranjan-dsai/batchhelm-ai#readme";

const navItems = [
  { label: "Recalls", icon: AlertTriangle, path: "/" },
  { label: "Inventory", icon: Warehouse, path: "/inventory" },
  { label: "Tasks", icon: ClipboardCheck, path: "/tasks" },
  { label: "Agents", icon: BarChart3, path: "/agents" },
  { label: "Evidence", icon: FileText, path: "/evidence" },
  { label: "Memory", icon: Brain, path: "/memory" },
];

export function App() {
  const orchestrationController = useOrchestrationRun();
  const { session: orchestrationSession, rerun: rerunOrchestration } = orchestrationController;
  const intakeController = useIntakeWorkspace({
    onRunAccepted: orchestrationController.adoptRun,
  });

  const location = useLocation();
  const [searchQuery, setSearchQuery] = useState("");
  const [provider, setProvider] = useState<ProviderStatus | null>(null);
  const [providerProof, setProviderProof] = useState<QwenVerificationReceipt | null>(null);
  const [providerEvidenceState, setProviderEvidenceState] = useState<ProviderProofState>("unavailable");
  const searchRef = useRef<HTMLInputElement>(null);

  // Demo data state
  const [incident, setIncident] = useState(demoIncident);
  const [tasks, setTasks] = useState(demoIncident.tasks);
  const [inspection, setInspection] = useState<ShelfInspectionResult | null>(null);
  const [inspectionState, setInspectionState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [inspectionError, setInspectionError] = useState("");
  const [packet, setPacket] = useState<EvidencePacket | null>(null);
  const [packetState, setPacketState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [packetError, setPacketError] = useState("");
  const [review, setReview] = useState<EvidenceReviewState | null>(null);
  const [reviewState, setReviewState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [reviewError, setReviewError] = useState("");

  useEffect(() => {
    let active = true;
    fetchDashboardSync()
      .then((sync) => {
        if (!active) return;
        setProvider(sync.provider);
        setProviderProof(sync.proof);
        setProviderEvidenceState(sync.proofState);
      })
      .catch(() => {
        if (active) setProviderEvidenceState("unavailable");
      });
    return () => { active = false; };
  }, []);

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

  const refreshEvidence = useCallback((signal?: AbortSignal) => {
    setPacketState("loading");
    setReviewState("loading");
    setPacketError("");
    setReviewError("");

    fetchEvidencePacket(signal)
      .then((data) => {
        setPacket(data);
        setPacketState("ready");
      })
      .catch((error) => {
        if (error.name === "AbortError") return;
        setPacketError(error instanceof Error ? error.message : "Failed to load evidence packet");
        setPacketState("error");
      });

    fetchEvidenceReview(signal)
      .then((data) => {
        setReview(data);
        setReviewState("ready");
      })
      .catch((error) => {
        if (error.name === "AbortError") return;
        setReviewError(error instanceof Error ? error.message : "Failed to load evidence review");
        setReviewState("error");
      });
  }, []);

  useEffect(() => {
    if (location.pathname !== "/evidence") return;
    const controller = new AbortController();
    refreshEvidence(controller.signal);
    return () => controller.abort();
  }, [location.pathname, refreshEvidence]);

  const toggleTask = (taskId: string) => {
    setTasks((current) =>
      current.map((task) =>
        task.id === taskId
          ? { ...task, status: task.status === "complete" ? "in-progress" : "complete" }
          : task,
      ),
    );
  };

  const assignOpenTasksToMe = () => {
    setTasks((current) =>
      current.map((task) =>
        task.status === "complete" ? task : { ...task, assignee: "Operations Manager", initials: "OM" },
      ),
    );
  };

  const openTaskCount = tasks.filter((task) => task.status !== "complete").length;

  return (
    <div className="app-shell">
      <Sidebar activePath={location.pathname} openTaskCount={openTaskCount} />
      <div className="workspace">
        <TopBar
          incident={incident}
          provider={provider}
          providerProof={providerProof}
          providerEvidenceState={providerEvidenceState}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          openTaskCount={openTaskCount}
          searchRef={searchRef}
        />
        <main className="dashboard" aria-label="Recall command center">
          <Suspense fallback={<PageLoader />}>
            <Routes>
            <Route
              path="/"
              element={<Dashboard incident={incident} onNewRecall={intakeController.open} />}
            />
            <Route path="/inventory" element={<InventoryPage inventory={incident.inventory} />} />
            <Route
              path="/agents"
              element={
                <AgentsPage
                  session={{
                    accepted: orchestrationSession.accepted,
                    result: orchestrationSession.result,
                    events: orchestrationSession.events,
                    connected: orchestrationSession.connection === "streaming" || orchestrationSession.connection === "completed",
                    error: orchestrationSession.error || null,
                  }}
                  onRerun={rerunOrchestration}
                />
              }
            />
            <Route
              path="/tasks"
              element={
                <TasksPage
                  tasks={tasks}
                  onToggleTask={toggleTask}
                  onAssignToMe={assignOpenTasksToMe}
                />
              }
            />
            <Route
              path="/evidence"
              element={
                <EvidencePage
                  evidence={incident.evidence}
                  packet={packet}
                  packetState={packetState}
                  packetError={packetError}
                  review={review}
                  reviewState={reviewState}
                  reviewError={reviewError}
                  inspection={inspection}
                  inspectionState={inspectionState}
                  inspectionError={inspectionError}
                  onRefresh={() => refreshEvidence()}
                  onReviewDecision={(decision: ReviewDecision) => {
                    setReviewState("loading");
                    setReviewError("");
                    submitReviewDecision(decision)
                      .then((data) => {
                        setReview(data);
                        setReviewState("ready");
                      })
                      .catch((error) => {
                        setReviewError(error instanceof Error ? error.message : "Review decision failed");
                        setReviewState("error");
                      });
                  }}
                  onDemoInspection={() => {
                    setInspectionState("loading");
                    setInspectionError("");
                    fetchDemoInspection()
                      .then((data) => {
                        setInspection(data);
                        setInspectionState("ready");
                      })
                      .catch((error) => {
                        setInspectionError(error instanceof Error ? error.message : "Demo inspection failed");
                        setInspectionState("error");
                      });
                  }}
                  onUploadInspection={(file: File) => {
                    setInspectionState("loading");
                    setInspectionError("");
                    uploadShelfPhoto(file)
                      .then((data) => {
                        setInspection(data);
                        setInspectionState("ready");
                      })
                      .catch((error) => {
                        setInspectionError(error instanceof Error ? error.message : "Shelf inspection failed");
                        setInspectionState("error");
                      });
                  }}
                />
              }
            />
            <Route path="/timeline" element={<TimelinePage workflow={incident.workflow} />} />
            <Route path="/memory" element={<MemoryPage insights={incident.insights} />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
        </main>
      </div>
      <MobileNav activePath={location.pathname} openTaskCount={openTaskCount} />
      <IntakeWorkspace controller={intakeController} />
    </div>
  );
}

function PageLoader() {
  return (
    <div className="page-loader" role="status" aria-label="Loading page">
      <span className="page-loader-spinner" aria-hidden="true" />
      <span>Loading page...</span>
    </div>
  );
}

function MobileNav({ activePath, openTaskCount }: { activePath: string; openTaskCount: number }) {
  return (
    <nav className="mobile-nav" aria-label="Mobile navigation">
      {navItems.map((item) => {
        const Icon = item.icon;
        const selected = activePath === item.path || (item.path !== "/" && activePath.startsWith(item.path));
        return (
          <Link
            key={item.label}
            to={item.path}
            className={`mobile-nav-item ${selected ? "selected" : ""}`}
            aria-current={selected ? "page" : undefined}
          >
            <Icon size={20} />
            <span>{item.label}</span>
            {item.label === "Tasks" && openTaskCount > 0 ? (
              <span className="mobile-nav-badge">{openTaskCount}</span>
            ) : null}
          </Link>
        );
      })}
    </nav>
  );
}

function Sidebar({ activePath, openTaskCount }: { activePath: string; openTaskCount: number }) {
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
          const selected = activePath === item.path || (item.path !== "/" && activePath.startsWith(item.path));
          return (
            <Link
              key={item.label}
              to={item.path}
              className={`nav-item ${selected ? "selected" : ""}`}
              aria-current={selected ? "page" : undefined}
            >
              <Icon size={21} />
              <span>{item.label}</span>
              {item.label === "Tasks" ? (
                <span className="nav-badge">{openTaskCount}</span>
              ) : null}
            </Link>
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
        <a className="footer-link" href={helpUrl} target="_blank" rel="noreferrer">
          <HelpCircle size={20} />
          <span>Help & Support</span>
        </a>
        <Link to="/settings" className="footer-link">
          <Settings size={20} />
          <span>Settings</span>
        </Link>
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
  searchRef,
}: {
  incident: typeof demoIncident;
  provider: ProviderStatus | null;
  providerProof: QwenVerificationReceipt | null;
  providerEvidenceState: ProviderProofState;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  openTaskCount: number;
  searchRef: React.Ref<HTMLInputElement>;
}) {
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
        <div className="dropdown">
          <button type="button" className="icon-button" aria-label="Notifications">
            <Bell size={20} />
            {openTaskCount > 0 && <span className="notification-badge">{openTaskCount}</span>}
          </button>
        </div>
        <div className="profile-button">
          <span className="avatar">OM</span>
          <span className="profile-copy">
            <strong>Operations Manager</strong>
            <span>Central Foods Co.</span>
          </span>
          <ChevronDown size={16} />
        </div>
      </div>
    </header>
  );
}
