// @vitest-environment jsdom

import { act, renderHook, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "./api";
import type {
  OrchestrationResult,
  OrchestrationRunAccepted,
} from "./api";
import {
  ORCHESTRATION_SESSION_KEY,
  useOrchestrationRun,
} from "./useOrchestrationRun";

class MockEventSource {
  static instances: MockEventSource[] = [];

  readonly url: string;
  readonly listeners = new Map<string, Set<EventListener>>();
  readonly close = vi.fn();
  onerror: ((event: Event) => void) | null = null;

  constructor(url: string | URL) {
    this.url = String(url);
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: EventListener): void {
    const listeners = this.listeners.get(type) ?? new Set<EventListener>();
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }

  emit(type: string, payload: unknown): void {
    const event = new MessageEvent(type, {
      data: JSON.stringify(payload),
    });
    for (const listener of this.listeners.get(type) ?? []) {
      listener(event);
    }
  }
}

const accepted: OrchestrationRunAccepted = {
  run_id: "run-1",
  incident_id: "recall-spinach-2026-06",
  status: "pending",
  events_url: "/api/orchestration/runs/run-1/events",
  result_url: "/api/orchestration/runs/run-1",
};

const orchestrationResult = {
  run_id: "run-1",
  incident_id: "recall-spinach-2026-06",
  status: "completed",
  provider_mode: "demo-fallback",
  started_at: "2026-06-30T09:00:00+00:00",
  finished_at: "2026-06-30T09:00:01+00:00",
  duration_ms: 1000,
  agents: [],
  events: [],
  analysis: {},
  briefing: {
    headline: "Recall contained",
    situation: "Affected inventory is quarantined.",
    actions: [],
    risks: [],
    next_review: "",
    confidence: 90,
    source: "deterministic",
    provider: "qwen",
    used_fallback: true,
  },
  memory_writes: 1,
  conflicts_resolved: 0,
  summary: "Complete",
} as unknown as OrchestrationResult;

describe("useOrchestrationRun", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    sessionStorage.clear();
    vi.restoreAllMocks();
    vi.stubGlobal("EventSource", MockEventSource);
    vi.stubGlobal("crypto", {
      randomUUID: vi
        .fn()
        .mockReturnValueOnce("request-1")
        .mockReturnValueOnce("request-2"),
    });
  });

  it("shows the cached latest run on mount without starting a run", async () => {
    const start = vi.spyOn(api, "startDemoRun").mockResolvedValue(accepted);
    const latest = vi.spyOn(api, "fetchLatestRun").mockResolvedValue({
      run_id: "run-1",
      incident_id: "recall-spinach-2026-06",
      status: "completed",
      provider_mode: "demo-fallback",
      started_at: "2026-06-30T09:00:00+00:00",
      updated_at: "2026-06-30T09:00:01+00:00",
      finished_at: "2026-06-30T09:00:01+00:00",
      result: orchestrationResult,
    });

    const { result } = renderHook(() => useOrchestrationRun());

    await waitFor(() => {
      expect(result.current.session.result).toEqual(orchestrationResult);
    });
    expect(result.current.session.connection).toBe("completed");
    expect(latest).toHaveBeenCalled();
    expect(start).not.toHaveBeenCalled();
    expect(MockEventSource.instances).toHaveLength(0);
  });

  it("stays idle on mount when no cached run exists", async () => {
    const start = vi.spyOn(api, "startDemoRun").mockResolvedValue(accepted);
    const latest = vi.spyOn(api, "fetchLatestRun").mockResolvedValue(null);

    const { result } = renderHook(() => useOrchestrationRun());

    await waitFor(() => expect(latest).toHaveBeenCalled());
    expect(result.current.session.connection).toBe("idle");
    expect(start).not.toHaveBeenCalled();
    expect(MockEventSource.instances).toHaveLength(0);
  });

  it("starts one request when React Strict Mode remounts after rerun", async () => {
    vi.spyOn(api, "fetchLatestRun").mockResolvedValue(null);
    const start = vi.spyOn(api, "startDemoRun").mockResolvedValue(accepted);

    const { result } = renderHook(() => useOrchestrationRun(), {
      wrapper: StrictMode,
    });
    expect(start).not.toHaveBeenCalled();

    act(() => result.current.rerun());

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });
    expect(start).toHaveBeenCalledTimes(1);
  });

  it("reconnects a stored run without starting another", async () => {
    sessionStorage.setItem(
      ORCHESTRATION_SESSION_KEY,
      JSON.stringify(accepted),
    );
    const start = vi.spyOn(api, "startDemoRun").mockResolvedValue(accepted);
    const latest = vi.spyOn(api, "fetchLatestRun").mockResolvedValue(null);

    renderHook(() => useOrchestrationRun());

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });
    expect(start).not.toHaveBeenCalled();
    expect(latest).not.toHaveBeenCalled();
    expect(MockEventSource.instances[0].url).toContain(accepted.run_id);
  });

  it("creates one new request each time rerun is selected", async () => {
    vi.spyOn(api, "fetchLatestRun").mockResolvedValue(null);
    const start = vi
      .spyOn(api, "startDemoRun")
      .mockResolvedValueOnce(accepted)
      .mockResolvedValueOnce({
        ...accepted,
        run_id: "run-2",
        events_url: "/api/orchestration/runs/run-2/events",
        result_url: "/api/orchestration/runs/run-2",
      });

    const { result } = renderHook(() => useOrchestrationRun());
    expect(start).not.toHaveBeenCalled();

    act(() => result.current.rerun());
    await waitFor(() => expect(start).toHaveBeenCalledTimes(1));

    act(() => result.current.rerun());
    await waitFor(() => expect(start).toHaveBeenCalledTimes(2));
    expect(start.mock.calls.map(([requestId]) => requestId)).toEqual([
      "request-1",
      "request-2",
    ]);
  });

  it("adopts an intake run without starting a demo run", async () => {
    vi.spyOn(api, "fetchLatestRun").mockResolvedValue(null);
    const start = vi.spyOn(api, "startDemoRun").mockResolvedValue(accepted);
    const { result } = renderHook(() => useOrchestrationRun());
    const intakeAccepted = {
      ...accepted,
      run_id: "run-intake",
      incident_id: "incident-intake",
      events_url: "/api/orchestration/runs/run-intake/events",
      result_url: "/api/orchestration/runs/run-intake",
    };

    act(() => result.current.adoptRun(intakeAccepted));

    await waitFor(() => {
      expect(MockEventSource.instances.at(-1)?.url).toContain(
        intakeAccepted.run_id,
      );
    });
    expect(start).not.toHaveBeenCalled();
  });
});
