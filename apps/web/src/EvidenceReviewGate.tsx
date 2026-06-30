import {
  AlertCircle,
  Check,
  CheckCircle2,
  Clock3,
  MessageSquareWarning,
  ShieldCheck,
} from "lucide-react";
import type {
  EvidenceReviewState,
  ReviewChecklistStatus,
  ReviewDecision,
  ReviewStatus,
} from "./types";

interface EvidenceReviewGateProps {
  review: EvidenceReviewState;
  isSubmitting: boolean;
  onDecision: (decision: ReviewDecision) => void;
}

const reviewStatusLabels: Record<ReviewStatus, string> = {
  pending: "Pending",
  "needs-changes": "Needs Changes",
  approved: "Approved",
};

export function EvidenceReviewGate({
  review,
  isSubmitting,
  onDecision,
}: EvidenceReviewGateProps) {
  return (
    <section className="review-gate" aria-labelledby="review-gate-title">
      <header className="review-summary">
        <div className="review-summary-copy">
          <div className="review-title-line">
            <ShieldCheck size={18} aria-hidden="true" />
            <h3 id="review-gate-title">Submission Review</h3>
            <span className={`review-status ${review.status}`}>
              {reviewStatusLabels[review.status]}
            </span>
          </div>
          <p>{review.next_action}</p>
        </div>
        <div
          className={`review-readiness ${
            review.ready_to_submit ? "ready" : "blocked"
          }`}
        >
          <strong>
            {review.ready_to_submit
              ? "Ready"
              : `${review.blocker_count} blocker${
                  review.blocker_count === 1 ? "" : "s"
                }`}
          </strong>
          <span>Regulatory release</span>
        </div>
      </header>

      <div className="review-content-grid">
        <div className="review-section">
          <h4>Release checks</h4>
          <div className="review-checklist">
            {review.checklist.map((item) => (
              <div className="review-check-row" key={item.id}>
                <ReviewCheckIcon status={item.status} />
                <div>
                  <strong>{item.label}</strong>
                  <span>{item.detail}</span>
                </div>
                <em className={item.status}>
                  {formatChecklistStatus(item.status)}
                </em>
              </div>
            ))}
          </div>
        </div>

        <div className="review-section">
          <h4>Audit trail</h4>
          <div className="review-timeline">
            {review.timeline.slice(-4).map((event) => (
              <div className="review-event" key={event.id}>
                <span
                  className={`review-event-dot ${event.status}`}
                  aria-hidden="true"
                />
                <div>
                  <strong>{event.title}</strong>
                  <span>{event.detail}</span>
                </div>
                <div className="review-event-meta">
                  <strong>{event.actor}</strong>
                  <span>{formatReviewTimestamp(event.at)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="review-actions" aria-live="polite">
        <button
          type="button"
          className="review-button secondary"
          disabled={isSubmitting || review.status === "needs-changes"}
          onClick={() => onDecision("needs-changes")}
        >
          <MessageSquareWarning size={16} />
          Request changes
        </button>
        <button
          type="button"
          className="review-button primary"
          disabled={isSubmitting || review.status === "approved"}
          onClick={() => onDecision("approved")}
        >
          <CheckCircle2 size={16} />
          {isSubmitting ? "Applying decision" : "Approve packet"}
        </button>
      </div>
    </section>
  );
}

function ReviewCheckIcon({ status }: { status: ReviewChecklistStatus }) {
  if (status === "passed") {
    return (
      <span className="review-check-icon passed" aria-hidden="true">
        <Check size={13} />
      </span>
    );
  }
  if (status === "blocked") {
    return (
      <span className="review-check-icon blocked" aria-hidden="true">
        <AlertCircle size={14} />
      </span>
    );
  }
  return (
    <span className="review-check-icon attention" aria-hidden="true">
      <Clock3 size={14} />
    </span>
  );
}

function formatChecklistStatus(status: ReviewChecklistStatus) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function formatReviewTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("en", {
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}
