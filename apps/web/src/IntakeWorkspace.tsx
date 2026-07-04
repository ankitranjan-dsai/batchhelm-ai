import {
  AlertTriangle,
  ArrowLeft,
  Check,
  CheckCircle2,
  FileText,
  Image,
  LoaderCircle,
  Rocket,
  ShieldCheck,
  Table2,
  Upload,
  X,
} from "lucide-react";
import { useEffect, type ReactNode } from "react";
import type {
  IntakeFieldEvidence,
  PublicIntakeArtifact,
  RecallCriteriaDraft,
} from "./api";
import type { useIntakeWorkspace } from "./useIntakeWorkspace";

export type IntakeWorkspaceController = ReturnType<
  typeof useIntakeWorkspace
>;

interface IntakeWorkspaceProps {
  controller: IntakeWorkspaceController;
}

const stages = ["files", "review", "launch"] as const;

export function IntakeWorkspace({
  controller,
}: IntakeWorkspaceProps) {
  const { isOpen, session } = controller;

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        controller.close();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [controller.close, isOpen]);

  if (!isOpen) {
    return null;
  }

  return (
    <div className="intake-backdrop">
      <section
        className="intake-workspace"
        role="dialog"
        aria-modal="true"
        aria-labelledby="intake-title"
      >
        <header className="intake-header">
          <h2 id="intake-title">New recall</h2>
          <button
            type="button"
            className="icon-button"
            aria-label="Close intake"
            onClick={controller.close}
          >
            <X size={20} />
          </button>
        </header>

        <StageRail stage={session.stage} />

        <div className="intake-content">
          {session.stage === "files" ? (
            <FilesStage controller={controller} />
          ) : session.stage === "processing" ? (
            <ProcessingStage controller={controller} />
          ) : session.stage === "review" ? (
            <ReviewStage controller={controller} />
          ) : (
            <LaunchStage controller={controller} />
          )}
        </div>

        <footer className="intake-actions">
          <StageActions controller={controller} />
        </footer>
      </section>
    </div>
  );
}

function StageRail({
  stage,
}: {
  stage: IntakeWorkspaceController["session"]["stage"];
}) {
  const visibleStage = stage === "processing" ? "files" : stage;
  const activeIndex = stages.indexOf(visibleStage);
  return (
    <nav className="intake-stages" aria-label="Intake stages">
      {stages.map((item, index) => {
        const complete = index < activeIndex;
        const active = index === activeIndex;
        return (
          <div
            key={item}
            className={`intake-stage ${active ? "active" : ""} ${
              complete ? "complete" : ""
            }`}
            aria-current={active ? "step" : undefined}
          >
            <span className="intake-stage-dot">
              {complete ? <Check size={14} /> : null}
            </span>
            <span>{titleCase(item)}</span>
          </div>
        );
      })}
    </nav>
  );
}

function FilesStage({
  controller,
}: {
  controller: IntakeWorkspaceController;
}) {
  const { files } = controller.session;
  const errors = fileErrors(files);
  return (
    <div className="intake-files-stage">
      <div className="intake-section-heading">
        <div>
          <h3>Incident files</h3>
          <p>Upload the source packet used to create this recall.</p>
        </div>
        <span>24 MB packet limit</span>
      </div>

      <div className="intake-file-list">
        <FileControl
          id="intake-notice"
          label="Recall notice"
          detail="PDF, text, JPEG, PNG, or WebP"
          accept=".pdf,.txt,image/jpeg,image/png,image/webp"
          file={files.notice}
          icon={<FileText size={20} />}
          error={errors.notice}
          onChange={(notice) =>
            controller.selectFiles({ ...files, notice })
          }
        />
        <FileControl
          id="intake-inventory"
          label="Inventory CSV"
          detail="Required structured inventory export"
          accept=".csv,text/csv"
          file={files.inventory}
          icon={<Table2 size={20} />}
          error={errors.inventory}
          onChange={(inventory) =>
            controller.selectFiles({ ...files, inventory })
          }
        />
        <FileControl
          id="intake-shelf"
          label="Shelf photo"
          detail="Optional JPEG, PNG, or WebP evidence"
          accept="image/jpeg,image/png,image/webp"
          file={files.shelfPhoto}
          icon={<Image size={20} />}
          error={errors.shelfPhoto}
          optional
          onChange={(shelfPhoto) =>
            controller.selectFiles({ ...files, shelfPhoto })
          }
        />
      </div>

      <div className="intake-processing-summary">
        <ShieldCheck size={20} />
        <div>
          <strong>Files stay attached to this incident</strong>
          <span>
            Content hashes, source names, and evidence locators are preserved.
          </span>
        </div>
      </div>
      <InlineError message={controller.session.error} />
    </div>
  );
}

interface FileControlProps {
  id: string;
  label: string;
  detail: string;
  accept: string;
  file: File | null;
  icon: ReactNode;
  error: string;
  optional?: boolean;
  onChange: (file: File | null) => void;
}

function FileControl({
  id,
  label,
  detail,
  accept,
  file,
  icon,
  error,
  optional = false,
  onChange,
}: FileControlProps) {
  return (
    <div className={`intake-file-control ${error ? "invalid" : ""}`}>
      <div className="intake-file-icon">{icon}</div>
      <div className="intake-file-copy">
        <label htmlFor={id}>
          {label}
          {optional ? <span>Optional</span> : null}
        </label>
        <small>{file ? `${file.name} · ${formatBytes(file.size)}` : detail}</small>
        {error ? <em>{error}</em> : null}
      </div>
      <label className="intake-file-command" htmlFor={id}>
        <Upload size={16} />
        <span>{file ? "Replace" : "Choose"}</span>
      </label>
      <input
        id={id}
        type="file"
        accept={accept}
        onChange={(event) => onChange(event.currentTarget.files?.[0] ?? null)}
      />
    </div>
  );
}

function ProcessingStage({
  controller,
}: {
  controller: IntakeWorkspaceController;
}) {
  const view = controller.session.view;
  return (
    <div className="intake-processing-stage" aria-live="polite">
      <LoaderCircle className="spin" size={32} />
      <h3>Processing incident files</h3>
      <p>
        {view?.status === "uploaded"
          ? "Packet stored. Extraction is queued."
          : "Reading notice evidence and normalizing inventory."}
      </p>
      <div className="intake-processing-files">
        {[controller.session.files.notice, controller.session.files.inventory]
          .filter((file): file is File => file !== null)
          .map((file) => (
            <span key={file.name}>
              <CheckCircle2 size={15} />
              {file.name}
            </span>
          ))}
      </div>
      <InlineError message={controller.session.error} />
    </div>
  );
}

function ReviewStage({
  controller,
}: {
  controller: IntakeWorkspaceController;
}) {
  const { criteria, view } = controller.session;
  if (criteria === null || view?.draft === null || view?.draft === undefined) {
    return <InlineError message="Extracted intake data is unavailable." />;
  }
  const draft = view.draft;
  return (
    <div className="intake-review-grid">
      <section className="intake-criteria" aria-labelledby="criteria-title">
        <div className="intake-section-heading compact">
          <div>
            <h3 id="criteria-title">Recall details</h3>
            <p>Verify every safety-critical field before launch.</p>
          </div>
        </div>

        <CriteriaField
          label="Product name"
          field="product_name"
          controller={controller}
        >
          <input
            id="criteria-product-name"
            value={criteria.product_name}
            onChange={(event) =>
              controller.editCriteria("product_name", event.target.value)
            }
          />
        </CriteriaField>
        <CriteriaField
          label="Affected lots"
          field="affected_lots"
          controller={controller}
        >
          <textarea
            id="criteria-affected-lots"
            rows={2}
            value={criteria.affected_lots.join(", ")}
            onChange={(event) =>
              controller.editCriteria(
                "affected_lots",
                commaList(event.target.value),
              )
            }
          />
        </CriteriaField>
        <CriteriaField label="UPCs" field="upcs" controller={controller}>
          <input
            id="criteria-upcs"
            value={criteria.upcs.join(", ")}
            onChange={(event) =>
              controller.editCriteria("upcs", commaList(event.target.value))
            }
          />
        </CriteriaField>
        <CriteriaField
          label="Risk level"
          field="risk_level"
          controller={controller}
        >
          <select
            id="criteria-risk-level"
            value={criteria.risk_level ?? ""}
            onChange={(event) =>
              controller.editCriteria(
                "risk_level",
                (event.target.value || null) as RecallCriteriaDraft["risk_level"],
              )
            }
          >
            <option value="">Select risk</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
        </CriteriaField>
        <CriteriaField
          label="Reason"
          field="reason"
          controller={controller}
        >
          <textarea
            id="criteria-reason"
            rows={3}
            value={criteria.reason}
            onChange={(event) =>
              controller.editCriteria("reason", event.target.value)
            }
          />
        </CriteriaField>
        <CriteriaField
          label="Source"
          field="source"
          controller={controller}
        >
          <input
            id="criteria-source"
            value={criteria.source}
            onChange={(event) =>
              controller.editCriteria("source", event.target.value)
            }
          />
        </CriteriaField>
      </section>

      <section className="intake-inventory-review" aria-labelledby="inventory-title">
        <div className="intake-section-heading compact">
          <div>
            <h3 id="inventory-title">Inventory import</h3>
            <p>Validated rows from the uploaded CSV.</p>
          </div>
        </div>
        <div className="intake-import-metrics">
          <ImportMetric
            tone="success"
            value={`${draft.import_summary.accepted_rows} accepted`}
          />
          <ImportMetric
            tone={draft.import_summary.rejected_rows > 0 ? "danger" : "muted"}
            value={`${draft.import_summary.rejected_rows} rejected`}
          />
          <ImportMetric
            tone="muted"
            value={`${draft.import_summary.stores} stores`}
          />
          <ImportMetric
            tone={draft.import_summary.warnings.length > 0 ? "warning" : "muted"}
            value={`${draft.import_summary.warnings.length} warnings`}
          />
        </div>

        <div className="intake-table-wrap">
          <table className="intake-table">
            <thead>
              <tr>
                <th>Store</th>
                <th>Product</th>
                <th>Lot</th>
                <th>On hand</th>
                <th>Location</th>
              </tr>
            </thead>
            <tbody>
              {controller.session.inventory.slice(0, 10).map((row) => (
                <tr key={row.id}>
                  <td>{row.store}</td>
                  <td>{row.product}</td>
                  <td>{row.lot}</td>
                  <td>{row.on_hand}</td>
                  <td>{row.location || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {draft.import_summary.warnings.length > 0 ? (
          <div className="intake-warning-list">
            {draft.import_summary.warnings.map((warning) => (
              <p key={warning}>
                <AlertTriangle size={15} />
                {warning}
              </p>
            ))}
          </div>
        ) : null}

        <ShelfEvidence view={view} />
        <InlineError message={controller.session.error} />
      </section>
    </div>
  );
}

function CriteriaField({
  label,
  field,
  controller,
  children,
}: {
  label: string;
  field: keyof RecallCriteriaDraft;
  controller: IntakeWorkspaceController;
  children: ReactNode;
}) {
  const evidence = latestEvidence(
    controller.session.view?.evidence ?? [],
    `criteria.${field}`,
  );
  const artifact = artifactFor(
    controller.session.view?.artifacts ?? [],
    evidence?.artifact_id ?? null,
  );
  const id = `criteria-${field.replace("_", "-")}`;
  return (
    <div className="intake-field">
      <label htmlFor={id}>{label}</label>
      {children}
      <div className="intake-provenance">
        <span>
          {evidence
            ? `${
                artifact?.original_filename ??
                (evidence.source === "reviewer"
                  ? "Reviewer correction"
                  : "Source notice")
              } · ${evidence.locator}`
            : "No extracted evidence"}
        </span>
        {evidence ? <strong>{evidence.confidence}% confidence</strong> : null}
      </div>
    </div>
  );
}

function ImportMetric({
  value,
  tone,
}: {
  value: string;
  tone: "success" | "danger" | "warning" | "muted";
}) {
  return (
    <span className={`intake-import-metric ${tone}`}>
      {tone === "success" ? (
        <CheckCircle2 size={15} />
      ) : tone === "danger" || tone === "warning" ? (
        <AlertTriangle size={15} />
      ) : (
        <Table2 size={15} />
      )}
      {value}
    </span>
  );
}

function ShelfEvidence({
  view,
}: {
  view: NonNullable<IntakeWorkspaceController["session"]["view"]>;
}) {
  const result = view.draft?.shelf_inspection;
  const label =
    result?.recall_match === true
      ? "Match"
      : result?.recall_match === false
        ? "No match"
        : "Unknown";
  return (
    <div className="intake-shelf-evidence">
      <div className="intake-shelf-icon">
        <Image size={22} />
      </div>
      <div>
        <span>Shelf evidence</span>
        <strong>{label}</strong>
        <p>
          {result?.recommended_action ??
            "No shelf photo was included with this packet."}
        </p>
      </div>
    </div>
  );
}

function LaunchStage({
  controller,
}: {
  controller: IntakeWorkspaceController;
}) {
  const { view, criteria, inventory } = controller.session;
  if (view === null || criteria === null) {
    return <InlineError message="Reviewed intake data is unavailable." />;
  }
  return (
    <div className="intake-launch-stage">
      <div className="intake-launch-title">
        <div className="intake-launch-icon">
          <ShieldCheck size={24} />
        </div>
        <div>
          <h3>Ready to start the recall workflow</h3>
          <p>
            Confirmation creates an immutable incident snapshot before agents run.
          </p>
        </div>
      </div>

      <dl className="intake-launch-summary">
        <div>
          <dt>Product</dt>
          <dd>{criteria.product_name}</dd>
        </div>
        <div>
          <dt>Affected lots</dt>
          <dd>{criteria.affected_lots.join(", ") || "None"}</dd>
        </div>
        <div>
          <dt>UPCs</dt>
          <dd>{criteria.upcs.join(", ") || "None"}</dd>
        </div>
        <div>
          <dt>Risk</dt>
          <dd>{criteria.risk_level ? titleCase(criteria.risk_level) : "Unset"}</dd>
        </div>
        <div>
          <dt>Inventory</dt>
          <dd>
            {inventory.length} rows across {view.draft?.stores.length ?? 0} stores
          </dd>
        </div>
        <div>
          <dt>Provider</dt>
          <dd>{view.provider_mode}</dd>
        </div>
      </dl>

      <div className="intake-launch-note">
        <Rocket size={20} />
        <div>
          <strong>Durable agent run</strong>
          <p>
            Progress, events, review history, and shelf evidence survive refresh
            and restart.
          </p>
        </div>
      </div>
      <InlineError message={controller.session.error} />
    </div>
  );
}

function StageActions({
  controller,
}: {
  controller: IntakeWorkspaceController;
}) {
  const { session } = controller;
  const errors = fileErrors(session.files);
  if (session.stage === "files") {
    const disabled =
      session.files.notice === null ||
      session.files.inventory === null ||
      Boolean(errors.notice || errors.inventory || errors.shelfPhoto) ||
      session.operation === "uploading";
    return (
      <>
        <span />
        <button
          type="button"
          className="intake-primary-button"
          disabled={disabled}
          onClick={() => void controller.processFiles()}
        >
          {session.operation === "uploading" ? (
            <LoaderCircle className="spin" size={17} />
          ) : (
            <Upload size={17} />
          )}
          Process files
        </button>
      </>
    );
  }
  if (session.stage === "processing") {
    return (
      <>
        <button
          type="button"
          className="intake-secondary-button"
          onClick={controller.close}
        >
          Close
        </button>
        <span className="intake-action-status">Processing continues in the background</span>
      </>
    );
  }
  if (session.stage === "review") {
    const valid = criteriaComplete(session.criteria);
    return (
      <>
        <button
          type="button"
          className="intake-secondary-button"
          onClick={controller.reset}
        >
          <ArrowLeft size={17} />
          Back
        </button>
        <div className="intake-action-group">
          <button
            type="button"
            className="intake-secondary-button"
            disabled={
              session.dirtyFields.length === 0 ||
              session.operation === "saving"
            }
            onClick={() => void controller.saveDraft()}
          >
            {session.operation === "saving" ? (
              <LoaderCircle className="spin" size={17} />
            ) : null}
            Save corrections
          </button>
          <button
            type="button"
            className="intake-primary-button"
            disabled={session.dirtyFields.length > 0 || !valid}
            onClick={controller.continueToLaunch}
          >
            Continue
          </button>
        </div>
      </>
    );
  }
  return (
    <>
      <button
        type="button"
        className="intake-secondary-button"
        onClick={controller.backToReview}
      >
        <ArrowLeft size={17} />
        Back
      </button>
      <button
        type="button"
        className="intake-primary-button"
        disabled={session.operation === "launching"}
        onClick={() => void controller.launch()}
      >
        {session.operation === "launching" ? (
          <LoaderCircle className="spin" size={17} />
        ) : (
          <Rocket size={17} />
        )}
        {session.operation === "launching"
          ? "Starting agent workflow"
          : "Confirm and run agents"}
      </button>
    </>
  );
}

function InlineError({ message }: { message: string }) {
  return message ? (
    <div className="intake-error" role="alert">
      <AlertTriangle size={17} />
      {message}
    </div>
  ) : null;
}

function latestEvidence(
  evidence: IntakeFieldEvidence[],
  fieldPath: string,
): IntakeFieldEvidence | null {
  return (
    [...evidence].reverse().find((item) => item.field_path === fieldPath) ??
    null
  );
}

function artifactFor(
  artifacts: PublicIntakeArtifact[],
  id: string | null,
): PublicIntakeArtifact | null {
  return artifacts.find((item) => item.id === id) ?? null;
}

function criteriaComplete(criteria: RecallCriteriaDraft | null): boolean {
  return Boolean(
    criteria?.product_name.trim() &&
      (criteria.affected_lots.length > 0 || criteria.upcs.length > 0) &&
      criteria.risk_level &&
      criteria.reason.trim() &&
      criteria.source.trim(),
  );
}

function commaList(value: string): string[] {
  const seen = new Set<string>();
  return value
    .split(",")
    .map((item) => item.trim())
    .filter((item) => {
      const key = item.toLocaleLowerCase();
      if (!item || seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
}

function fileErrors(files: IntakeWorkspaceController["session"]["files"]) {
  return {
    notice:
      files.notice && files.notice.size > 12 * 1024 * 1024
        ? "Recall notice exceeds 12 MB."
        : "",
    inventory:
      files.inventory && files.inventory.size > 4 * 1024 * 1024
        ? "Inventory CSV exceeds 4 MB."
        : "",
    shelfPhoto:
      files.shelfPhoto && files.shelfPhoto.size > 8 * 1024 * 1024
        ? "Shelf photo exceeds 8 MB."
        : "",
  };
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${Math.round(bytes / 1024)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
