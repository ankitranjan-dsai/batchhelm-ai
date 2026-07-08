import { useState, useMemo } from "react";
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Check,
  FileCheck2,
  FilePlus2,
  Mail,
  PackageCheck,
  Shield,
  Brain,
  CalendarDays,
} from "lucide-react";
import { Link } from "react-router-dom";
import type { RecallIncident, RecallMetric, AgentActivity, MemoryInsight, Milestone, WorkflowStep } from "../types";
import { Metric, PanelHeader, getEvidenceProgress } from "./shared";

interface DashboardProps {
  incident: RecallIncident;
  onNewRecall: () => void;
}

export function Dashboard({ incident, onNewRecall }: DashboardProps) {
  const evidenceProgress = getEvidenceProgress(incident.evidence);

  return (
    <div className="dashboard-page">
      {/* Incident Summary Card */}
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
          <Link to="/" className="action-button active">
            <Shield size={18} />
            <span>Command Center</span>
          </Link>
          <Link to="/inventory" className="action-button">
            <PackageCheck size={18} />
            <span>Quarantine</span>
            <em>In Progress</em>
          </Link>
          <Link to="/evidence" className="action-button">
            <Mail size={18} />
            <span>Customer Notice</span>
            <em>Draft</em>
          </Link>
          <Link to="/evidence" className="action-button">
            <FileCheck2 size={18} />
            <span>Compliance Packet</span>
            <em>In Progress</em>
          </Link>
          <button
            type="button"
            className="action-button new-recall-button"
            onClick={onNewRecall}
          >
            <FilePlus2 size={18} />
            <span>New recall</span>
          </button>
        </div>
      </section>

      {/* Dashboard Grid */}
      <section className="dashboard-grid">
        {/* Quick Timeline Preview */}
        <section className="panel timeline-panel" aria-labelledby="timeline-title">
          <PanelHeader
            title="Agent Workflow Timeline"
            actionLabel="View full timeline"
          />
          <div className="timeline" id="timeline-title">
            {incident.workflow.slice(0, 5).map((step) => (
              <div className="timeline-item" key={step.id}>
                <span className={`timeline-dot ${step.status}`} aria-hidden="true">
                  {step.status === "complete" ? <Check size={13} /> : null}
                </span>
                <div className="timeline-copy">
                  <strong>{step.title}</strong>
                  <span>{step.detail}</span>
                </div>
                <time>{step.time}</time>
              </div>
            ))}
          </div>
          <Link to="/timeline" className="inline-link">
            View full timeline
            <ArrowRight size={15} />
          </Link>
        </section>

        {/* Quick Inventory Preview */}
        <section className="panel inventory-panel" aria-labelledby="inventory-preview-title">
          <PanelHeader
            title="Affected Inventory"
            actionLabel="View all"
          />
          <div className="table-wrap compact">
            <table>
              <thead>
                <tr>
                  <th scope="col">Store</th>
                  <th scope="col">SKU</th>
                  <th scope="col">Lot</th>
                  <th scope="col">Quarantined</th>
                </tr>
              </thead>
              <tbody>
                {incident.inventory.slice(0, 5).map((row) => (
                  <tr key={row.id}>
                    <td>{row.store}</td>
                    <td>{row.sku}</td>
                    <td>{row.lot}</td>
                    <td>{row.quarantined}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Link to="/inventory" className="inline-link">
            View all inventory
            <ArrowRight size={15} />
          </Link>
        </section>
      </section>

      {/* Lower Grid */}
      <section className="lower-grid">
        {/* Agent Activity Preview */}
        <section className="panel rail-panel" aria-labelledby="agents-title">
          <PanelHeader
            title="Live Agent Activity"
            actionLabel="View all"
          />
          <div className="rail-list" id="agents-title">
            {incident.agents.slice(0, 5).map((agent, index) => (
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
          <Link to="/agents" className="inline-link">
            Go to Mission Control
            <ArrowRight size={15} />
          </Link>
        </section>

        {/* Memory Insights Preview */}
        <section className="panel rail-panel" aria-labelledby="memory-title">
          <PanelHeader
            title="Memory Insights"
            actionLabel="View all"
          />
          <div className="memory-list" id="memory-title">
            {incident.insights.slice(0, 3).map((insight, index) => (
              <div className="memory-row" key={insight.id}>
                <span className={`memory-icon ${insight.tone}`} aria-hidden="true">
                  {index === 0 ? (
                    <Shield size={20} />
                  ) : index === 1 ? (
                    <BarChart3 size={20} />
                  ) : (
                    <Brain size={20} />
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

        {/* Next Milestones */}
        <section className="panel milestone-panel" aria-labelledby="milestones-title">
          <PanelHeader title="Next Milestones" />
          <div className="milestone-list" id="milestones-title">
            {incident.milestones.slice(0, 3).map((milestone) => (
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
          <Link to="/tasks" className="inline-link">
            View task board
            <ArrowRight size={15} />
          </Link>
        </section>
      </section>
    </div>
  );
}
