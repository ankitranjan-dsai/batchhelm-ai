// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { IntakeView } from "./api";
import {
  IntakeWorkspace,
  type IntakeWorkspaceController,
} from "./IntakeWorkspace";
import { initialIntakeSession } from "./intakeSession";

function reviewView(): IntakeView {
  return {
    intake_id: "intake-1",
    status: "review_required",
    version: 1,
    provider_mode: "live",
    created_at: "2026-07-04T08:00:00+00:00",
    updated_at: "2026-07-04T08:01:00+00:00",
    artifacts: [
      {
        id: "notice-1",
        role: "recall_notice",
        original_filename: "notice.pdf",
        media_type: "application/pdf",
        size_bytes: 2048,
        sha256: "a".repeat(64),
      },
    ],
    draft: {
      criteria: {
        product_name: "Spinach 10 oz",
        affected_lots: ["L2418", "L2419"],
        upcs: ["008500001010"],
        risk_level: "high",
        reason: "Possible contamination",
        source: "Central Farms",
      },
      notice_text: "Spinach 10 oz",
      inventory: [
        {
          id: "inventory-row-2",
          store: "Store A",
          sku: "SPN10Z",
          product: "Spinach 10 oz",
          lot: "L2418",
          upc: "008500001010",
          on_hand: 6,
          location: "Cooler",
          supplier_alias: "Central Farms",
        },
      ],
      stores: ["Store A"],
      import_summary: {
        accepted_rows: 1,
        rejected_rows: 1,
        stores: 1,
        mapped_headers: { "Store Name": "store" },
        warnings: ["Row 3 was rejected because on_hand is invalid."],
      },
      shelf_inspection: {
        upload: {
          original_filename: "shelf.png",
          media_type: "image/png",
          size_bytes: 1024,
        },
        extracted: {
          product_name: "",
          lot_code: "",
          upc: "",
          best_by: null,
          confidence: 0,
        },
        recall_match: null,
        recommended_action: "Review the uploaded shelf image manually.",
        review_required: true,
        evidence_note: "No image match was inferred.",
        provider: "qwen",
        used_fallback: true,
      },
      review_required: true,
    },
    evidence: [
      {
        id: "evidence-1",
        intake_id: "intake-1",
        field_path: "criteria.product_name",
        value: "Spinach 10 oz",
        artifact_id: "notice-1",
        locator: "page 1",
        source: "qwen",
        confidence: 96,
        requires_review: false,
        supersedes_id: null,
        created_at: "2026-07-04T08:01:00+00:00",
      },
    ],
    incident_id: null,
    run_id: null,
    error_code: null,
    error_message: null,
  };
}

function controller(
  stage: "files" | "review" | "launch",
): IntakeWorkspaceController {
  const view = stage === "files" ? null : reviewView();
  return {
    isOpen: true,
    session: {
      ...initialIntakeSession,
      stage,
      view,
      criteria: view?.draft?.criteria ?? null,
      inventory: view?.draft?.inventory ?? [],
      serverVersion: view?.version ?? -1,
    },
    open: vi.fn(),
    close: vi.fn(),
    selectFiles: vi.fn(),
    processFiles: vi.fn(),
    editCriteria: vi.fn(),
    saveDraft: vi.fn(),
    confirm: vi.fn(),
    continueToLaunch: vi.fn(),
    backToReview: vi.fn(),
    launch: vi.fn(),
    reset: vi.fn(),
    receive: vi.fn(),
  };
}

describe("IntakeWorkspace", () => {
  it("requires notice and inventory before processing", () => {
    render(<IntakeWorkspace controller={controller("files")} />);

    const button = screen.getByRole("button", {
      name: "Process files",
    }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(screen.getByLabelText("Recall notice")).toBeTruthy();
    expect(screen.getByLabelText("Inventory CSV")).toBeTruthy();
  });

  it("shows provenance and editable extracted criteria", () => {
    const value = controller("review");
    render(<IntakeWorkspace controller={value} />);

    const product = screen.getByLabelText(
      "Product name",
    ) as HTMLInputElement;
    expect(product.value).toBe("Spinach 10 oz");
    expect(screen.getByText("notice.pdf · page 1")).toBeTruthy();
    expect(screen.getByText("96% confidence")).toBeTruthy();
    expect(screen.getByText("Unknown")).toBeTruthy();
    expect(screen.getByText("1 accepted")).toBeTruthy();
    expect(screen.getByText("1 rejected")).toBeTruthy();

    const lots = screen.getByLabelText("Affected lots");
    fireEvent.change(lots, {
      target: { value: " L2418, L2419, L2418 " },
    });

    expect(value.editCriteria).toHaveBeenCalledWith("affected_lots", [
      "L2418",
      "L2419",
    ]);
  });

  it("launches the confirmed run from the Launch stage", () => {
    const value = controller("launch");
    render(<IntakeWorkspace controller={value} />);

    fireEvent.click(
      screen.getByRole("button", {
        name: "Confirm and run agents",
      }),
    );

    expect(value.launch).toHaveBeenCalledTimes(1);
  });
});
