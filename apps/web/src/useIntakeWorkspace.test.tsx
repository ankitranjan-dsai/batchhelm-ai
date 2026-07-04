// @vitest-environment jsdom

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "./api";
import { useIntakeWorkspace } from "./useIntakeWorkspace";

const accepted: api.IntakeAccepted = {
  intake_id: "intake-1",
  status: "uploaded",
  status_url: "/api/intakes/intake-1",
  created_at: "2026-07-04T08:00:00+00:00",
};

const runAccepted: api.OrchestrationRunAccepted = {
  run_id: "run-1",
  incident_id: "incident-1",
  status: "pending",
  events_url: "/api/orchestration/runs/run-1/events",
  result_url: "/api/orchestration/runs/run-1",
};

const selectedFiles = {
  notice: new File(["notice"], "notice.txt", { type: "text/plain" }),
  inventory: new File(["inventory"], "inventory.csv", {
    type: "text/csv",
  }),
  shelfPhoto: null,
};

function intakeView(
  overrides: Partial<api.IntakeView> = {},
): api.IntakeView {
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

describe("useIntakeWorkspace", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.restoreAllMocks();
    vi.stubGlobal("crypto", {
      randomUUID: vi.fn().mockReturnValue("request-1"),
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("creates one intake and polls until review", async () => {
    const create = vi
      .spyOn(api, "createIntakePacket")
      .mockResolvedValue(accepted);
    vi.spyOn(api, "fetchIntake")
      .mockResolvedValueOnce(
        intakeView({ status: "extracting", version: 0 }),
      )
      .mockResolvedValueOnce(
        intakeView({ status: "review_required", version: 1 }),
      );

    const { result } = renderHook(() => useIntakeWorkspace());
    act(() => {
      result.current.open();
      result.current.selectFiles(selectedFiles);
    });
    await act(async () => {
      await result.current.processFiles();
    });
    await act(async () => {
      await Promise.resolve();
    });
    expect(api.fetchIntake).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(800);
    });

    expect(create).toHaveBeenCalledTimes(1);
    expect(result.current.session.stage).toBe("review");
  });

  it("closing the workspace stops polling without cancelling the intake", async () => {
    vi.spyOn(api, "createIntakePacket").mockResolvedValue(accepted);
    const fetch = vi
      .spyOn(api, "fetchIntake")
      .mockResolvedValue(
        intakeView({ status: "extracting", version: 0 }),
      );
    const { result } = renderHook(() => useIntakeWorkspace());
    act(() => {
      result.current.open();
      result.current.selectFiles(selectedFiles);
    });
    await act(async () => {
      await result.current.processFiles();
    });
    await act(async () => {
      await Promise.resolve();
    });
    expect(fetch).toHaveBeenCalledTimes(1);

    act(() => result.current.close());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1600);
    });

    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("confirms and launches under one command", async () => {
    const onRunAccepted = vi.fn();
    vi.spyOn(api, "confirmIntake").mockResolvedValue(
      intakeView({
        status: "ready",
        version: 2,
        incident_id: "incident-1",
      }),
    );
    vi.spyOn(api, "startIntakeRun").mockResolvedValue({
      intake: intakeView({
        status: "run_started",
        version: 3,
        incident_id: "incident-1",
        run_id: "run-1",
      }),
      run: runAccepted,
    });
    const { result } = renderHook(() =>
      useIntakeWorkspace({ onRunAccepted }),
    );
    act(() => {
      result.current.open();
      result.current.receive(intakeView());
      result.current.continueToLaunch();
    });

    await act(async () => {
      await result.current.launch();
    });

    expect(api.confirmIntake).toHaveBeenCalledTimes(1);
    expect(api.startIntakeRun).toHaveBeenCalledTimes(1);
    expect(onRunAccepted).toHaveBeenCalledWith(runAccepted);
    expect(result.current.isOpen).toBe(false);
  });
});
