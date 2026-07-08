import { Check } from "lucide-react";
import type { WorkflowStep } from "../types";
import { PanelHeader } from "./shared";

interface TimelinePageProps {
  workflow: WorkflowStep[];
}

export function TimelinePage({ workflow }: TimelinePageProps) {
  return (
    <div className="page-content">
      <div className="page-header">
        <h1>Agent Workflow Timeline</h1>
        <p className="page-subtitle">
          Full execution trace of the recall response workflow
        </p>
      </div>

      <section className="panel timeline-panel full-width" aria-labelledby="timeline-title">
        <PanelHeader title={`${workflow.length} Workflow Steps`} />
        <div className="timeline timeline-full" id="timeline-title">
          {workflow.map((step, index) => (
            <div className="timeline-item" key={step.id}>
              <span className="timeline-number">{index + 1}</span>
              <span className={`timeline-dot ${step.status}`} aria-hidden="true">
                {step.status === "complete" ? <Check size={13} /> : null}
              </span>
              <div className="timeline-copy">
                <strong>{step.title}</strong>
                <span>{step.detail}</span>
              </div>
              <time>{step.time}</time>
              <span className={`timeline-status ${step.status}`}>
                {step.status}
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
