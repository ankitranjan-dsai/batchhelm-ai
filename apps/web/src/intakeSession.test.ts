import { describe, expect, it } from "vitest";
import type { IntakeView } from "./api";
import {
  initialIntakeSession,
  intakeSessionReducer,
} from "./intakeSession";

export function intakeView(
  overrides: Partial<IntakeView> = {},
): IntakeView {
  return {
    intake_id: "intake-1",
    status: "review_required",
    version: 1,
    provider_mode: "demo-fallback",
    created_at: "2026-07-04T08:00:00+00:00",
    updated_at: "2026-07-04T08:01:00+00:00",
    artifacts: [],
    draft: {
      criteria: {
        product_name: "Spinach 10 oz",
        affected_lots: ["L2418"],
        upcs: ["008500001010"],
        risk_level: "high",
        reason: "Possible contamination",
        source: "Central Farms",
      },
      notice_text: "Spinach 10 oz lot L2418",
      inventory: [],
      stores: ["Store A"],
      import_summary: {
        accepted_rows: 0,
        rejected_rows: 0,
        stores: 1,
        mapped_headers: {},
        warnings: [],
      },
      shelf_inspection: null,
      review_required: true,
    },
    evidence: [],
    incident_id: null,
    run_id: null,
    error_code: null,
    error_message: null,
    ...overrides,
  };
}

describe("intakeSessionReducer", () => {
  it("moves from files to review only for a reviewable persisted intake", () => {
    const state = intakeSessionReducer(initialIntakeSession, {
      type: "received",
      intake: intakeView({ status: "review_required", version: 1 }),
    });

    expect(state.stage).toBe("review");
    expect(state.serverVersion).toBe(1);
  });

  it("ignores stale poll responses", () => {
    const current = {
      ...initialIntakeSession,
      view: intakeView({ status: "review_required", version: 3 }),
      criteria: intakeView().draft?.criteria ?? null,
      serverVersion: 3,
      stage: "review" as const,
    };
    const state = intakeSessionReducer(current, {
      type: "received",
      intake: intakeView({ status: "extracting", version: 2 }),
    });

    expect(state.serverVersion).toBe(3);
    expect(state.view?.status).toBe("review_required");
  });

  it("marks locally edited criteria as dirty", () => {
    const review = intakeSessionReducer(initialIntakeSession, {
      type: "received",
      intake: intakeView(),
    });
    const state = intakeSessionReducer(review, {
      type: "edit-criteria",
      field: "product_name",
      value: "Corrected Spinach",
    });

    expect(state.criteria?.product_name).toBe("Corrected Spinach");
    expect(state.dirtyFields).toContain("criteria.product_name");
  });

  it("preserves dirty edits when a same-version poll arrives", () => {
    const review = intakeSessionReducer(initialIntakeSession, {
      type: "received",
      intake: intakeView({ version: 2 }),
    });
    const edited = intakeSessionReducer(review, {
      type: "edit-criteria",
      field: "product_name",
      value: "Corrected Spinach",
    });
    const state = intakeSessionReducer(edited, {
      type: "received",
      intake: intakeView({ version: 2 }),
    });

    expect(state.criteria?.product_name).toBe("Corrected Spinach");
    expect(state.dirtyFields).toContain("criteria.product_name");
  });
});
