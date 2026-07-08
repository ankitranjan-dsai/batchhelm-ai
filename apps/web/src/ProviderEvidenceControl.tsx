import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  AlertTriangle,
  Cloud,
  ShieldCheck,
  X,
  type LucideIcon,
} from "lucide-react";
import type {
  ProviderProofState,
  ProviderStatus,
  QwenVerificationReceipt,
} from "./api";

export type ProviderEvidenceState = "loading" | ProviderProofState;

interface ProviderEvidenceControlProps {
  provider: ProviderStatus | null;
  proof: QwenVerificationReceipt | null;
  state: ProviderEvidenceState;
}

interface EvidenceStatus {
  key: "checking" | "verified" | "configured" | "fallback" | "unavailable";
  label: string;
  summary: string;
  icon: LucideIcon;
}

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

function resolveEvidenceStatus(
  provider: ProviderStatus | null,
  proof: QwenVerificationReceipt | null,
  state: ProviderEvidenceState,
): EvidenceStatus {
  if (state === "loading") {
    return {
      key: "checking",
      label: "Checking",
      summary: "Provider evidence is loading.",
      icon: Cloud,
    };
  }
  if (provider?.mode === "demo-fallback") {
    return {
      key: "fallback",
      label: "Fallback",
      summary: "Deterministic fallback is active. No live provider claim is shown.",
      icon: Cloud,
    };
  }
  if (state === "unavailable" || provider === null) {
    return {
      key: "unavailable",
      label: "Unavailable",
      summary: "Provider proof could not be loaded.",
      icon: AlertTriangle,
    };
  }
  if (state === "verified" && proof?.verified) {
    return {
      key: "verified",
      label: "Verified",
      summary: "A successful Qwen Cloud call has a persisted redacted receipt.",
      icon: ShieldCheck,
    };
  }
  return {
    key: "configured",
    label: "Configured",
    summary:
      "Live credentials are configured, but no successful verification receipt is available.",
    icon: Cloud,
  };
}

function formatUtc(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  const day = String(date.getUTCDate()).padStart(2, "0");
  const month = MONTHS[date.getUTCMonth()];
  const year = date.getUTCFullYear();
  const hour = String(date.getUTCHours()).padStart(2, "0");
  const minute = String(date.getUTCMinutes()).padStart(2, "0");
  return `${day} ${month} ${year}, ${hour}:${minute} UTC`;
}

export function ProviderEvidenceControl({
  provider,
  proof,
  state,
}: ProviderEvidenceControlProps) {
  const [isOpen, setIsOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const status = resolveEvidenceStatus(provider, proof, state);
  const StatusIcon = status.icon;

  const closeDialog = (restoreFocus = false) => {
    setIsOpen(false);
    if (restoreFocus) {
      window.setTimeout(() => triggerRef.current?.focus(), 0);
    }
  };

  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeDialog(true);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [isOpen]);

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className={`provider-evidence-trigger ${status.key}`}
        aria-label={`Qwen Cloud evidence: ${status.key}`}
        disabled={state === "loading"}
        onClick={() => setIsOpen(true)}
      >
        <StatusIcon size={17} aria-hidden="true" />
        <span className="provider-evidence-copy">
          <span>Qwen Cloud</span>
          <strong>{status.label}</strong>
        </span>
      </button>

      {isOpen
        ? createPortal(
            <div
              className="provider-evidence-backdrop"
              onMouseDown={(event) => {
                if (event.currentTarget === event.target) {
                  closeDialog(true);
                }
              }}
            >
              <section
                className="provider-evidence-dialog"
                role="dialog"
                aria-modal="true"
                aria-labelledby="provider-evidence-title"
              >
                <header className="provider-evidence-header">
                  <div>
                    <span className="provider-evidence-overline">
                      Provider receipt
                    </span>
                    <h2 id="provider-evidence-title">Qwen Cloud evidence</h2>
                  </div>
                  <button
                    type="button"
                    className="icon-button provider-evidence-close"
                    aria-label="Close Qwen Cloud evidence"
                    autoFocus
                    onClick={() => closeDialog(true)}
                  >
                    <X size={18} aria-hidden="true" />
                  </button>
                </header>

                <div className={`provider-evidence-summary ${status.key}`}>
                  <StatusIcon size={20} aria-hidden="true" />
                  <div>
                    <strong>{status.label}</strong>
                    <p>{status.summary}</p>
                  </div>
                </div>

                {proof && status.key === "verified" ? (
                  <dl className="provider-evidence-details">
                    <div>
                      <dt>Model</dt>
                      <dd>{proof.model}</dd>
                    </div>
                    <div>
                      <dt>Verified at</dt>
                      <dd>{formatUtc(proof.verified_at)}</dd>
                    </div>
                    <div>
                      <dt>Latency</dt>
                      <dd>{proof.latency_ms} ms</dd>
                    </div>
                    <div className="provider-evidence-wide">
                      <dt>Response fingerprint</dt>
                      <dd className="provider-evidence-mono">
                        {proof.response_sha256.slice(0, 16)}…
                      </dd>
                    </div>
                  </dl>
                ) : null}

                <p className="provider-evidence-footnote">
                  Receipt metadata is persisted without prompts, model output,
                  or credentials.
                </p>
              </section>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
