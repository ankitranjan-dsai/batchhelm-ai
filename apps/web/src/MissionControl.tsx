import { useEffect, useRef, useState } from "react";
import {
  orchestrationStreamUrl,
  type AgentRunEvent,
  type OrchestrationResult,
  type OutputSource,
} from "./api";

type RunState = "streaming" | "done" | "error";

const EVENT_TYPES = [
  "started",
  "reasoning",
  "output",
  "completed",
  "failed",
  "retry",
  "conflict",
  "resolved",
  "checkpoint",
  "orchestrator",
] as const;

const SOURCE_LABEL: Record<OutputSource, string> = {
  qwen: "Qwen",
  deterministic: "Deterministic",
  memory: "Memory",
  reviewer: "Reviewer",
};

const SOURCE_COLOR: Record<OutputSource, string> = {
  qwen: "#7c5cff",
  deterministic: "#64748b",
  memory: "#d9822b",
  reviewer: "#16a34a",
};

/**
 * Live agent mission control. Opens a Server-Sent Events stream to the
 * orchestration endpoint and renders each agent event as it happens, with a
 * badge showing whether the output came from Qwen, the deterministic fallback,
 * persistent memory, or a reviewer. On completion it shows the AI Showrunner
 * management briefing and run metadata.
 */
export function MissionControl() {
  const [events, setEvents] = useState<AgentRunEvent[]>([]);
  const [result, setResult] = useState<OrchestrationResult | null>(null);
  const [state, setState] = useState<RunState>("streaming");
  const [runKey, setRunKey] = useState(0);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    setEvents([]);
    setResult(null);
    setState("streaming");

    const source = new EventSource(orchestrationStreamUrl);
    sourceRef.current = source;

    for (const type of EVENT_TYPES) {
      source.addEventListener(type, (event) => {
        const parsed = JSON.parse((event as MessageEvent).data) as AgentRunEvent;
        setEvents((prev) => [...prev, parsed]);
      });
    }

    source.addEventListener("result", (event) => {
      const parsed = JSON.parse((event as MessageEvent).data) as OrchestrationResult;
      setResult(parsed);
      setState("done");
      source.close();
    });

    source.onerror = () => {
      setState((prev) => (prev === "done" ? prev : "error"));
      source.close();
    };

    return () => {
      source.close();
    };
  }, [runKey]);

  const liveMode = result?.provider_mode ?? "demo-fallback";

  return (
    <section
      style={{
        border: "1px solid rgba(148, 163, 184, 0.25)",
        borderRadius: 16,
        padding: 20,
        background: "rgba(15, 23, 42, 0.02)",
        display: "grid",
        gap: 16,
      }}
    >
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <div>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>
            Agent Mission Control
          </h2>
          <p style={{ margin: "4px 0 0", fontSize: 13, opacity: 0.7 }}>
            Live multi-agent recall response — streamed from the orchestrator.
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span
            style={{
              fontSize: 12,
              fontWeight: 600,
              padding: "4px 10px",
              borderRadius: 999,
              background:
                liveMode === "live"
                  ? "rgba(124, 92, 255, 0.15)"
                  : "rgba(100, 116, 139, 0.15)",
              color: liveMode === "live" ? "#7c5cff" : "#475569",
            }}
          >
            {liveMode === "live" ? "Qwen live" : "Demo fallback"}
          </span>
          <button
            type="button"
            onClick={() => setRunKey((key) => key + 1)}
            disabled={state === "streaming"}
            style={{
              fontSize: 13,
              fontWeight: 600,
              padding: "8px 14px",
              borderRadius: 10,
              border: "1px solid rgba(124, 92, 255, 0.4)",
              background: state === "streaming" ? "rgba(124,92,255,0.1)" : "#7c5cff",
              color: state === "streaming" ? "#7c5cff" : "white",
              cursor: state === "streaming" ? "default" : "pointer",
            }}
          >
            {state === "streaming" ? "Running…" : "Re-run agents"}
          </button>
        </div>
      </header>

      {result && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
            gap: 10,
          }}
        >
          <Metric label="Agents" value={`${result.agents.length}`} />
          <Metric label="Duration" value={`${result.duration_ms} ms`} />
          <Metric label="Conflicts resolved" value={`${result.conflicts_resolved}`} />
          <Metric label="Memory records" value={`${result.memory_writes}`} />
        </div>
      )}

      <div
        style={{
          maxHeight: 280,
          overflowY: "auto",
          display: "grid",
          gap: 8,
          paddingRight: 4,
        }}
      >
        {events.map((event) => (
          <div
            key={event.id}
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 10,
              fontSize: 13,
              padding: "8px 10px",
              borderRadius: 10,
              background: "rgba(148, 163, 184, 0.08)",
            }}
          >
            <SourceBadge source={event.source} />
            <div style={{ display: "grid", gap: 2 }}>
              <span style={{ fontWeight: 600 }}>
                {event.agent} · {event.type}
              </span>
              <span style={{ opacity: 0.8 }}>{event.message}</span>
            </div>
          </div>
        ))}
        {state === "error" && events.length === 0 && (
          <p style={{ fontSize: 13, color: "#dc2626" }}>
            Could not reach the orchestration stream. Is the API running?
          </p>
        )}
      </div>

      {result?.briefing && (
        <div
          style={{
            borderTop: "1px solid rgba(148, 163, 184, 0.2)",
            paddingTop: 14,
            display: "grid",
            gap: 8,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700 }}>
              AI Showrunner Briefing
            </h3>
            <SourceBadge source={result.briefing.source} />
          </div>
          <p style={{ margin: 0, fontWeight: 600 }}>{result.briefing.headline}</p>
          <p style={{ margin: 0, fontSize: 13, opacity: 0.85 }}>
            {result.briefing.situation}
          </p>
          {result.briefing.actions.length > 0 && (
            <ul style={{ margin: "2px 0 0", paddingLeft: 18, fontSize: 13 }}>
              {result.briefing.actions.map((action) => (
                <li key={action}>{action}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        padding: "10px 12px",
        borderRadius: 12,
        background: "rgba(148, 163, 184, 0.1)",
      }}
    >
      <div style={{ fontSize: 11, textTransform: "uppercase", opacity: 0.6 }}>
        {label}
      </div>
      <div style={{ fontSize: 18, fontWeight: 700 }}>{value}</div>
    </div>
  );
}

function SourceBadge({ source }: { source: OutputSource }) {
  return (
    <span
      style={{
        flexShrink: 0,
        fontSize: 11,
        fontWeight: 700,
        padding: "2px 8px",
        borderRadius: 999,
        color: "white",
        background: SOURCE_COLOR[source],
      }}
    >
      {SOURCE_LABEL[source]}
    </span>
  );
}
