import { describe, expect, it } from "vitest";
import {
  orchestrationEventsUrl,
  type AgentRunEvent,
  type OrchestrationResult,
  type OrchestrationRunAccepted,
} from "./api";
import {
  deriveAgentStates,
  initialOrchestrationSession,
  orchestrationSessionReducer,
} from "./orchestrationSession";

const event = (sequence: number): AgentRunEvent => ({
  id: `event-${sequence}`,
  run_id: "run-1",
  sequence,
  agent: "Recall Intake Agent",
  type: "reasoning",
  message: `event ${sequence}`,
  at: "2026-06-30T09:00:00+00:00",
  source: "deterministic",
  data: null,
});

describe("orchestrationSessionReducer", () => {
  it("deduplicates replayed events and keeps sequence order", () => {
    let state = initialOrchestrationSession;
    state = orchestrationSessionReducer(state, {
      type: "event",
      event: event(2),
    });
    state = orchestrationSessionReducer(state, {
      type: "event",
      event: event(1),
    });
    state = orchestrationSessionReducer(state, {
      type: "event",
      event: event(2),
    });

    expect(state.events.map((item) => item.sequence)).toEqual([1, 2]);
    expect(state.lastSequence).toBe(2);
  });

  it("restores a cached result with its events and completed connection", () => {
    const result = {
      run_id: "run-1",
      incident_id: "incident-1",
      status: "completed",
      events: [event(2), event(1)],
      summary: "Complete",
    } as unknown as OrchestrationResult;

    const state = orchestrationSessionReducer(initialOrchestrationSession, {
      type: "restored",
      result,
    });

    expect(state.connection).toBe("completed");
    expect(state.result).toBe(result);
    expect(state.events.map((item) => item.sequence)).toEqual([1, 2]);
    expect(state.lastSequence).toBe(2);
  });

  it("derives running and completed agent states from ordered events", () => {
    const states = deriveAgentStates([
      { ...event(1), agent: "Recall Intake Agent", type: "started" },
      { ...event(2), agent: "Recall Intake Agent", type: "completed" },
      { ...event(3), agent: "Document Extraction Agent", type: "started" },
    ]);

    expect(states["Recall Intake Agent"]).toBe("completed");
    expect(states["Document Extraction Agent"]).toBe("running");
  });
});

describe("orchestrationEventsUrl", () => {
  const accepted: OrchestrationRunAccepted = {
    run_id: "run-1",
    incident_id: "incident-1",
    status: "pending",
    events_url: "/api/orchestration/runs/run-1/events",
    result_url: "/api/orchestration/runs/run-1",
  };

  it("lets native EventSource own the initial reconnect cursor", () => {
    expect(orchestrationEventsUrl(accepted)).not.toContain("after=");
    expect(orchestrationEventsUrl(accepted, 4)).toContain("after=4");
  });
});
