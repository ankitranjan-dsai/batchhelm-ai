// @vitest-environment jsdom

import {
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type {
  ProviderStatus,
  QwenVerificationReceipt,
} from "./api";
import { ProviderEvidenceControl } from "./ProviderEvidenceControl";

const liveProvider: ProviderStatus = {
  provider: "qwen",
  configured: true,
  mode: "live",
};

const proof: QwenVerificationReceipt = {
  provider: "qwen-cloud",
  verified: true,
  model: "qwen3.7-plus",
  latency_ms: 142,
  response_sha256: "a".repeat(64),
  verified_at: "2026-07-05T01:30:00Z",
};

afterEach(cleanup);

describe("ProviderEvidenceControl", () => {
  it("opens the complete redacted verified receipt", () => {
    render(
      <ProviderEvidenceControl
        provider={liveProvider}
        proof={proof}
        state="verified"
      />,
    );

    const trigger = screen.getByRole("button", {
      name: "Qwen Cloud evidence: verified",
    });
    expect(screen.getByText("Verified")).toBeTruthy();

    fireEvent.click(trigger);

    const dialog = screen.getByRole("dialog", {
      name: "Qwen Cloud evidence",
    });
    expect(dialog).toBeTruthy();
    expect(dialog.parentElement?.parentElement).toBe(document.body);
    expect(screen.getByText("qwen3.7-plus")).toBeTruthy();
    expect(screen.getByText("142 ms")).toBeTruthy();
    expect(screen.getByText(/05 Jul 2026/)).toBeTruthy();
    expect(screen.getByText(/a{16}/)).toBeTruthy();
    expect(document.body.textContent).not.toContain("API key");
    expect(document.body.textContent).not.toContain('{"status":"verified"}');
  });

  it("distinguishes configured mode from verified execution", () => {
    render(
      <ProviderEvidenceControl
        provider={liveProvider}
        proof={null}
        state="not-verified"
      />,
    );

    expect(
      screen.getByRole("button", {
        name: "Qwen Cloud evidence: configured",
      }),
    ).toBeTruthy();
    expect(screen.getByText("Configured")).toBeTruthy();
  });

  it("shows deterministic fallback without a live claim", () => {
    render(
      <ProviderEvidenceControl
        provider={{ ...liveProvider, configured: false, mode: "demo-fallback" }}
        proof={null}
        state="not-verified"
      />,
    );

    expect(
      screen.getByRole("button", {
        name: "Qwen Cloud evidence: fallback",
      }),
    ).toBeTruthy();
    expect(screen.getByText("Fallback")).toBeTruthy();
  });

  it("shows unavailable proof and closes the dialog with Escape", () => {
    render(
      <ProviderEvidenceControl
        provider={liveProvider}
        proof={null}
        state="unavailable"
      />,
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Qwen Cloud evidence: unavailable",
      }),
    );
    expect(screen.getByRole("dialog")).toBeTruthy();

    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders a stable disabled loading state", () => {
    render(
      <ProviderEvidenceControl
        provider={null}
        proof={null}
        state="loading"
      />,
    );

    const trigger = screen.getByRole("button", {
      name: "Qwen Cloud evidence: checking",
    }) as HTMLButtonElement;
    expect(trigger.disabled).toBe(true);
    expect(screen.getByText("Checking")).toBeTruthy();
  });
});
