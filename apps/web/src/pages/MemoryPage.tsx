import { useEffect, useState } from "react";
import { BarChart3, Brain, RefreshCw, Shield } from "lucide-react";
import type { MemoryInsight } from "../types";
import { fetchMemoryRecords, type MemoryRecord } from "../api";
import { PanelHeader, formatPacketTimestamp } from "./shared";

interface MemoryPageProps {
  insights: MemoryInsight[];
}

const insightIcons = [Shield, BarChart3, Brain];

export function MemoryPage({ insights }: MemoryPageProps) {
  const [records, setRecords] = useState<MemoryRecord[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let active = true;
    setState("loading");
    setError("");
    fetchMemoryRecords()
      .then((data) => {
        if (!active) return;
        setRecords(data);
        setState("ready");
      })
      .catch((requestError) => {
        if (!active) return;
        setError(
          requestError instanceof Error ? requestError.message : "Failed to load memory records",
        );
        setState("error");
      });
    return () => {
      active = false;
    };
  }, [reloadToken]);

  return (
    <div className="page-content">
      <div className="page-header">
        <h1>Memory & Learned Patterns</h1>
        <div className="page-header-actions">
          <button
            type="button"
            className="utility-button"
            onClick={() => setReloadToken((token) => token + 1)}
            disabled={state === "loading"}
          >
            <RefreshCw size={16} />
            {state === "loading" ? "Syncing" : "Refresh"}
          </button>
        </div>
      </div>

      <section className="panel rail-panel full-width" aria-labelledby="insights-title">
        <PanelHeader
          title="Incident Insights"
          subtitle="What the agents flagged during this recall"
        />
        <div className="memory-list" id="insights-title">
          {insights.map((insight, index) => {
            const Icon = insightIcons[index % insightIcons.length];
            return (
              <div className="memory-row" key={insight.id}>
                <span className={`memory-icon ${insight.tone}`} aria-hidden="true">
                  <Icon size={20} />
                </span>
                <div>
                  <strong>{insight.title}</strong>
                  <p>{insight.detail}</p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="panel memory-records-panel full-width" aria-labelledby="records-title">
        <PanelHeader
          title="Learned Memory Records"
          subtitle="Patterns the agents persist across recall runs"
        />
        {state === "error" ? <p className="packet-error">{error}</p> : null}
        {state === "loading" ? (
          <div className="evidence-view-loading" role="status">
            <span aria-hidden="true" />
            Loading memory records
          </div>
        ) : null}
        {state === "ready" ? (
          records.length === 0 ? (
            <p className="empty-note">
              No learned memory yet. Run an orchestration to start building memory.
            </p>
          ) : (
            <div className="table-wrap compact" id="records-title">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Kind</th>
                    <th scope="col">Pattern</th>
                    <th scope="col">Learned Value</th>
                    <th scope="col">Detail</th>
                    <th scope="col">Confidence</th>
                    <th scope="col">Seen</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((record) => (
                    <tr key={record.id}>
                      <td>
                        <span className="memory-kind">{record.kind}</span>
                      </td>
                      <td>{record.key}</td>
                      <td>{record.value}</td>
                      <td>{record.detail}</td>
                      <td>{record.confidence}%</td>
                      <td>
                        {record.occurrences}&times; &middot; {formatPacketTimestamp(record.last_seen)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : null}
      </section>
    </div>
  );
}
