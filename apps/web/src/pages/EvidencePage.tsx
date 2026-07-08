import { useState } from "react";
import {
  ScanLine,
  FileCheck2,
  Download,
  RefreshCw,
} from "lucide-react";
import type { EvidenceItem, EvidencePacket, EvidenceReviewState } from "../types";
import type { ShelfInspectionResult } from "../api";
import { EvidenceReviewGate } from "../EvidenceReviewGate";
import { evidencePacketDownloadUrl } from "../api";
import { PanelHeader, getEvidenceProgress, formatEvidenceStatus, compactSectionBody, formatPacketTimestamp } from "./shared";

interface EvidencePageProps {
  evidence: EvidenceItem[];
  packet: EvidencePacket | null;
  packetState: "idle" | "loading" | "ready" | "error";
  packetError: string;
  review: EvidenceReviewState | null;
  reviewState: "idle" | "loading" | "ready" | "error";
  reviewError: string;
  inspection: ShelfInspectionResult | null;
  inspectionState: "idle" | "loading" | "ready" | "error";
  inspectionError: string;
  onRefresh: () => void;
  onReviewDecision: (decision: "approved" | "needs-changes") => void;
  onDemoInspection: () => void;
  onUploadInspection: (file: File) => void;
}

export function EvidencePage({
  evidence,
  packet,
  packetState,
  packetError,
  review,
  reviewState,
  reviewError,
  inspection,
  inspectionState,
  inspectionError,
  onRefresh,
  onReviewDecision,
  onDemoInspection,
  onUploadInspection,
}: EvidencePageProps) {
  const [activeView, setActiveView] = useState<"review" | "packet">("review");
  const progress = getEvidenceProgress(evidence);
  const isRefreshing = packetState === "loading" || reviewState === "loading";

  return (
    <div className="page-content">
      <div className="page-header">
        <h1>Evidence & Compliance</h1>
        <div className="page-header-actions">
          <button
            type="button"
            className="utility-button"
            onClick={onRefresh}
            disabled={isRefreshing}
          >
            <RefreshCw size={16} />
            {isRefreshing ? "Syncing" : "Refresh"}
          </button>
          <a className="utility-button" href={evidencePacketDownloadUrl}>
            <Download size={16} />
            Download .md
          </a>
        </div>
      </div>

      <div className="evidence-tabs">
        <button
          type="button"
          className={activeView === "review" ? "active" : ""}
          onClick={() => setActiveView("review")}
        >
          Review
        </button>
        <button
          type="button"
          className={activeView === "packet" ? "active" : ""}
          onClick={() => setActiveView("packet")}
        >
          Packet ({progress}%)
        </button>
      </div>

      {activeView === "review" ? (
        <section className="panel evidence-panel full-width">
          {reviewError ? <p className="packet-error">{reviewError}</p> : null}
          {review ? (
            <EvidenceReviewGate
              review={review}
              isSubmitting={reviewState === "loading"}
              onDecision={onReviewDecision}
            />
          ) : reviewState === "loading" ? (
            <div className="evidence-view-loading" role="status">
              <span aria-hidden="true" />
              Loading review controls
            </div>
          ) : null}
        </section>
      ) : (
        <section className="panel evidence-panel full-width">
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
                  <span className={`evidence-dot ${item.status}`} aria-hidden="true" />
                  <span>{item.label}</span>
                  <em>{formatEvidenceStatus(item.status)}</em>
                </div>
              ))}
            </div>
          </div>
          {packet ? (
            <div className="packet-preview" aria-label="Evidence packet preview">
              <div className="packet-preview-header">
                <strong>{packet.filename}</strong>
                <span>Generated {formatPacketTimestamp(packet.generated_at)}</span>
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
          ) : packetState === "loading" ? (
            <div className="evidence-view-loading" role="status">
              <span aria-hidden="true" />
              Generating packet preview
            </div>
          ) : null}
        </section>
      )}

      {/* Shelf Inspection Section */}
      <section className="panel inspection-panel full-width" aria-labelledby="inspection-title">
        <div className="panel-header with-actions">
          <h2 id="inspection-title">Shelf Inspection</h2>
          <button type="button" className="utility-button" onClick={onDemoInspection}>
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
                if (file) onUploadInspection(file);
                event.currentTarget.value = "";
              }}
            />
          </label>

          <div className={`inspection-result ${inspectionState}`}>
            {inspectionState === "loading" ? (
              <p>Inspecting label evidence...</p>
            ) : inspectionState === "error" ? (
              <p>{inspectionError}</p>
            ) : inspection ? (
              <>
                <div className="inspection-result-header">
                  <strong>
                    {inspection.recall_match ? "Recall match" : "Review needed"}
                  </strong>
                  <span>{inspection.extracted.confidence}% confidence</span>
                </div>
                <dl>
                  <div><dt>Product</dt><dd>{inspection.extracted.product_name}</dd></div>
                  <div><dt>Lot</dt><dd>{inspection.extracted.lot_code}</dd></div>
                  <div><dt>UPC</dt><dd>{inspection.extracted.upc}</dd></div>
                </dl>
                <p>{inspection.recommended_action}</p>
                <small>
                  {inspection.used_fallback ? "Demo fallback" : "Qwen vision"} · {inspection.upload.original_filename}
                </small>
              </>
            ) : (
              <p>No shelf image inspected yet.</p>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
