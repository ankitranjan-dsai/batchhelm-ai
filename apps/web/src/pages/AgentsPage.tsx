import { useState } from "react";
import {
  Activity,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Clock,
  PackageCheck,
  Mail,
  FileCheck2,
} from "lucide-react";
import type { AgentRunEvent, OrchestrationRunAccepted, OrchestrationResult } from "../api";

interface AgentsPageProps {
  session: {
    accepted: OrchestrationRunAccepted | null;
    result: OrchestrationResult | null;
    events: AgentRunEvent[];
    connected: boolean;
    error: string | null;
  };
  onRerun: () => void;
}

const agentIcons: Record<string, React.ReactNode> = {
  "Recall Intake Agent": <PackageCheck size={18} />,
  "Document Extraction Agent": <FileCheck2 size={18} />,
  "Inventory Matching Agent": <PackageCheck size={18} />,
  "Shelf Vision Agent": <Activity size={18} />,
  "Risk Scoring Agent": <AlertTriangle size={18} />,
  "Memory Agent": <Clock size={18} />,
  "Operations Task Agent": <PackageCheck size={18} />,
  "Communications Agent": <Mail size={18} />,
  "Compliance Evidence Agent": <FileCheck2 size={18} />,
  "Orchestrator Agent": <Activity size={18} />,
};

export function AgentsPage({ session, onRerun }: AgentsPageProps) {
  const [selectedWave, setSelectedWave] = useState<number | null>(null);

  const waves = [
    ["Recall Intake Agent"],
    ["Document Extraction Agent"],
    ["Inventory Matching Agent", "Shelf Vision Agent"],
    ["Risk Scoring Agent", "Memory Agent"],
    ["Operations Task Agent", "Communications Agent"],
    ["Compliance Evidence Agent"],
  ];

  const agentStatus: Record<string, { status: string; detail: string }> = {};
  session.result?.agents.forEach((a) => {
    agentStatus[a.agent] = { status: a.status, detail: a.summary };
  });

  return (
    <div className="page-content">
      <div className="page-header">
        <h1>Agent Mission Control</h1>
        <div className="page-header-actions">
          {session.connected ? (
            <span className="status-badge connected">
              <CheckCircle2 size={14} />
              Connected
            </span>
          ) : (
            <span className="status-badge reconnecting">
              <RefreshCw size={14} className="spin" />
              Reconnecting
            </span>
          )}
          <button type="button" className="utility-button" onClick={onRerun}>
            <RefreshCw size={16} />
            Restart Run
          </button>
        </div>
      </div>

      {session.accepted && (
        <div className="run-info">
          <span>Run ID: <code>{session.accepted.run_id.slice(0, 12)}</code></span>
          <span>Status: <strong>{session.accepted.status}</strong></span>
        </div>
      )}

      {/* Waves Grid */}
      <section className="waves-grid" aria-label="Agent execution waves">
        {waves.map((waveAgents, waveIndex) => (
          <div
            key={waveIndex}
            role="button"
            tabIndex={0}
            aria-pressed={selectedWave === waveIndex}
            aria-label={`Wave ${waveIndex + 1}: ${waveAgents.join(", ")}`}
            className={`wave-column ${selectedWave === waveIndex ? "selected" : ""}`}
            onClick={() => setSelectedWave(selectedWave === waveIndex ? null : waveIndex)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                setSelectedWave(selectedWave === waveIndex ? null : waveIndex);
              }
            }}
          >
            <h3 className="wave-title">Wave {waveIndex + 1}</h3>
            <div className="wave-agents">
              {waveAgents.map((agentName) => {
                const status = agentStatus[agentName];
                return (
                  <div
                    key={agentName}
                    className={`agent-card ${status?.status || "pending"}`}
                  >
                    <div className="agent-card-icon">
                      {agentIcons[agentName] || <Activity size={18} />}
                    </div>
                    <div className="agent-card-info">
                      <strong>{agentName.replace(" Agent", "")}</strong>
                      <span>{status?.status || "Pending"}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </section>

      {/* Wave / Agent Detail */}
      <section className="panel agent-detail-panel" aria-labelledby="wave-detail-title" aria-live="polite">
        {selectedWave === null ? (
          <>
            <div className="panel-header">
              <h2 id="wave-detail-title">Wave Details</h2>
            </div>
            <p className="empty-note">
              <Clock size={16} style={{ display: "inline", verticalAlign: "middle", marginRight: 6 }} />
              Select a wave above to inspect its agents, results, and events.
            </p>
          </>
        ) : (
          <>
            <div className="panel-header">
              <h2 id="wave-detail-title">Wave {selectedWave + 1} Details</h2>
              <span className="count-badge">
                {waves[selectedWave].length} agent{waves[selectedWave].length === 1 ? "" : "s"}
              </span>
            </div>
            <div className="wave-detail-list">
              {waves[selectedWave].map((agentName) => {
                const agentResult = session.result?.agents.find((a) => a.agent === agentName);
                const agentEvents = session.events.filter((e) => e.agent === agentName).slice(-4);
                const status = agentResult?.status ?? "pending";
                return (
                  <article className="wave-detail-card" key={agentName}>
                    <div className="wave-detail-heading">
                      <span className="agent-card-icon" aria-hidden="true">
                        {agentIcons[agentName] || <Activity size={18} />}
                      </span>
                      <strong>{agentName}</strong>
                      <span className={`state-pill ${status === "completed" ? "" : status}`}>
                        {status}
                      </span>
                    </div>
                    {agentResult ? (
                      <>
                        <p className="wave-detail-summary">{agentResult.summary}</p>
                        <small className="wave-detail-meta">
                          {agentResult.attempts} attempt{agentResult.attempts === 1 ? "" : "s"}
                          {" · "}
                          {agentResult.duration_ms} ms
                          {agentResult.depends_on.length > 0
                            ? ` · after ${agentResult.depends_on.join(", ")}`
                            : ""}
                        </small>
                      </>
                    ) : (
                      <p className="wave-detail-summary muted">
                        Waiting for this execution stage.
                      </p>
                    )}
                    {agentEvents.length > 0 ? (
                      <div className="wave-detail-events">
                        {agentEvents.map((event) => (
                          <div className="wave-detail-event" key={event.id}>
                            <span className="event-type">{event.type}</span>
                            <span>{event.message}</span>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </article>
                );
              })}
            </div>
          </>
        )}
      </section>

      {/* Execution Events */}
      <section className="panel events-panel" aria-labelledby="events-title">
        <div className="panel-header">
          <h2 id="events-title">Execution Events</h2>
          <span className="count-badge">{session.events.length}</span>
        </div>
        <div className="events-list">
          {session.events.length === 0 ? (
            <p className="empty-note">
              No execution events yet. Agents will appear here as they run.
            </p>
          ) : (
            session.events.map((event) => (
              <div key={event.id} className={`event-row ${event.type}`}>
                <span className="event-agent">{event.agent}</span>
                <span className="event-type">{event.type}</span>
                <span className="event-message">{event.message}</span>
                <time>{new Date(event.at).toLocaleTimeString()}</time>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
