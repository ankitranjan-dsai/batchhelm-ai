import {
  Activity,
  CheckCircle2,
  Circle,
  Clock3,
  RotateCcw,
  TriangleAlert,
  WifiOff,
} from "lucide-react";
import { useMemo, useState } from "react";
import type { AgentRunResult, OutputSource } from "./api";
import {
  deriveAgentStates,
  type AgentExecutionState,
  type OrchestrationSession,
} from "./orchestrationSession";

const WAVES = [
  ["Recall Intake Agent"],
  ["Document Extraction Agent"],
  ["Inventory Matching Agent", "Shelf Vision Agent"],
  ["Risk Scoring Agent", "Memory Agent"],
  ["Operations Task Agent", "Communications Agent"],
  ["Compliance Evidence Agent"],
] as const;

const SOURCE_LABEL: Record<OutputSource, string> = {
  qwen: "Qwen",
  deterministic: "Fallback",
  memory: "Memory",
  reviewer: "Reviewer",
};

const STATE_LABEL: Record<AgentExecutionState, string> = {
  pending: "Pending",
  running: "Running",
  completed: "Complete",
  failed: "Failed",
  skipped: "Skipped",
};

interface MissionControlProps {
  session: OrchestrationSession;
  onRerun: () => void;
}

export function MissionControl({
  session,
  onRerun,
}: MissionControlProps) {
  const [selectedAgent, setSelectedAgent] = useState<string>(
    "Recall Intake Agent",
  );
  const resultByAgent = useMemo(
    () =>
      new Map(
        (session.result?.agents ?? []).map((result) => [
          result.agent,
          result,
        ]),
      ),
    [session.result?.agents],
  );
  const eventStates = useMemo(
    () => deriveAgentStates(session.events),
    [session.events],
  );
  const selectedResult = resultByAgent.get(selectedAgent);
  const selectedEvents = session.events.filter(
    (event) => event.agent === selectedAgent,
  );
  const selectedLatest = selectedEvents[selectedEvents.length - 1];
  const canRerun =
    session.connection === "completed" || session.connection === "failed";

  function getAgentState(agent: string): AgentExecutionState {
    return resultByAgent.get(agent)?.status ?? eventStates[agent] ?? "pending";
  }

  return (
    <section className="mission-control" aria-labelledby="mission-title">
      <header className="mission-header">
        <div>
          <div className="mission-title-line">
            <Activity size={18} aria-hidden="true" />
            <h2 id="mission-title">Agent Mission Control</h2>
            <ConnectionBadge connection={session.connection} />
          </div>
          <p>
            {session.accepted
              ? `Run ${session.accepted.run_id.slice(0, 8)}`
              : "Preparing run"}
          </p>
        </div>
        <button
          type="button"
          className="mission-rerun"
          onClick={onRerun}
          disabled={!canRerun}
          aria-label="Run agents again"
          title="Run agents again"
        >
          <RotateCcw size={17} aria-hidden="true" />
        </button>
      </header>

      {session.result ? (
        <div className="mission-metrics" aria-label="Run metrics">
          <Metric label="Agents" value={String(session.result.agents.length)} />
          <Metric
            label="Duration"
            value={formatDuration(session.result.duration_ms)}
          />
          <Metric
            label="Conflicts"
            value={String(session.result.conflicts_resolved)}
          />
          <Metric
            label="Memory"
            value={String(session.result.memory_writes)}
          />
        </div>
      ) : null}

      <div className="mission-waves" aria-label="Agent execution graph">
        {WAVES.map((wave, waveIndex) => (
          <div className="mission-wave" key={`wave-${waveIndex + 1}`}>
            <span className="mission-wave-label">Wave {waveIndex + 1}</span>
            <div className="mission-wave-agents">
              {wave.map((agent) => {
                const state = getAgentState(agent);
                const result = resultByAgent.get(agent);
                return (
                  <button
                    type="button"
                    className={`mission-agent ${state} ${
                      selectedAgent === agent ? "selected" : ""
                    }`}
                    key={agent}
                    onClick={() => setSelectedAgent(agent)}
                    aria-pressed={selectedAgent === agent}
                  >
                    <AgentStateIcon state={state} />
                    <span>
                      <strong>{shortAgentName(agent)}</strong>
                      <small>{STATE_LABEL[state]}</small>
                    </span>
                    {result ? <SourceBadge source={result.source} /> : null}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="mission-detail-grid">
        <section
          className="mission-timeline"
          aria-labelledby="mission-events-title"
        >
          <div className="mission-section-heading">
            <h3 id="mission-events-title">Execution events</h3>
            <span>{session.events.length}</span>
          </div>
          <div className="mission-event-list" aria-live="polite">
            {session.events.length > 0 ? (
              session.events.slice(-18).map((event) => (
                <article className="mission-event" key={event.id}>
                  <SourceBadge source={event.source} />
                  <div>
                    <strong>
                      {shortAgentName(event.agent)}
                      <span>{event.type}</span>
                    </strong>
                    <p>{event.message}</p>
                  </div>
                  <time>{formatEventTime(event.at)}</time>
                </article>
              ))
            ) : (
              <MissionEmpty connection={session.connection} />
            )}
          </div>
        </section>

        <section
          className="mission-inspector"
          aria-labelledby="mission-inspector-title"
        >
          <div className="mission-section-heading">
            <h3 id="mission-inspector-title">{selectedAgent}</h3>
            <span className={`mission-state ${getAgentState(selectedAgent)}`}>
              {STATE_LABEL[getAgentState(selectedAgent)]}
            </span>
          </div>
          <AgentInspector
            result={selectedResult}
            latestMessage={selectedLatest?.message}
          />
        </section>
      </div>

      {session.error ? (
        <div className="mission-error" role="alert">
          <TriangleAlert size={17} aria-hidden="true" />
          <span>{session.error}</span>
        </div>
      ) : null}

      {session.result?.briefing ? (
        <section className="mission-briefing" aria-labelledby="briefing-title">
          <div className="mission-section-heading">
            <h3 id="briefing-title">Management briefing</h3>
            <SourceBadge source={session.result.briefing.source} />
          </div>
          <strong>{session.result.briefing.headline}</strong>
          <p>{session.result.briefing.situation}</p>
          {session.result.briefing.actions.length > 0 ? (
            <ul>
              {session.result.briefing.actions.map((action) => (
                <li key={action}>{action}</li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}
    </section>
  );
}

function AgentInspector({
  result,
  latestMessage,
}: {
  result: AgentRunResult | undefined;
  latestMessage: string | undefined;
}) {
  if (!result) {
    return (
      <div className="mission-inspector-empty">
        <Clock3 size={20} aria-hidden="true" />
        <p>{latestMessage ?? "Waiting for this execution stage."}</p>
      </div>
    );
  }

  return (
    <div className="mission-inspector-body">
      <dl className="mission-agent-metrics">
        <div>
          <dt>Confidence</dt>
          <dd>{result.confidence}%</dd>
        </div>
        <div>
          <dt>Duration</dt>
          <dd>{formatDuration(result.duration_ms)}</dd>
        </div>
        <div>
          <dt>Attempts</dt>
          <dd>{result.attempts}</dd>
        </div>
      </dl>
      <div className="mission-agent-summary">
        <span>Summary</span>
        <p>{result.summary}</p>
      </div>
      {result.reasoning ? (
        <div className="mission-agent-summary">
          <span>Reasoning</span>
          <p>{result.reasoning}</p>
        </div>
      ) : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="mission-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function SourceBadge({ source }: { source: OutputSource }) {
  return (
    <span className={`source-badge ${source}`}>{SOURCE_LABEL[source]}</span>
  );
}

function ConnectionBadge({
  connection,
}: {
  connection: OrchestrationSession["connection"];
}) {
  const labels: Record<OrchestrationSession["connection"], string> = {
    idle: "Idle",
    starting: "Starting",
    streaming: "Live",
    reconnecting: "Reconnecting",
    completed: "Complete",
    failed: "Failed",
  };
  return (
    <span className={`mission-connection ${connection}`}>
      {connection === "reconnecting" ? (
        <WifiOff size={12} aria-hidden="true" />
      ) : (
        <span aria-hidden="true" />
      )}
      {labels[connection]}
    </span>
  );
}

function AgentStateIcon({ state }: { state: AgentExecutionState }) {
  if (state === "completed") {
    return <CheckCircle2 size={17} aria-hidden="true" />;
  }
  if (state === "running") {
    return <Activity size={17} aria-hidden="true" />;
  }
  if (state === "failed") {
    return <TriangleAlert size={17} aria-hidden="true" />;
  }
  return <Circle size={17} aria-hidden="true" />;
}

function MissionEmpty({
  connection,
}: {
  connection: OrchestrationSession["connection"];
}) {
  return (
    <div className="mission-empty">
      <Activity size={20} aria-hidden="true" />
      <p>
        {connection === "failed"
          ? "No execution events were received."
          : "Waiting for the first agent event."}
      </p>
    </div>
  );
}

function shortAgentName(name: string) {
  return name.replace(" Agent", "");
}

function formatDuration(durationMs: number) {
  return durationMs < 1000
    ? `${durationMs} ms`
    : `${(durationMs / 1000).toFixed(1)} s`;
}

function formatEventTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
