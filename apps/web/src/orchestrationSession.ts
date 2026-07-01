import type {
  AgentRunEvent,
  OrchestrationResult,
  OrchestrationRunAccepted,
} from "./api";

export type OrchestrationConnection =
  | "idle"
  | "starting"
  | "streaming"
  | "reconnecting"
  | "completed"
  | "failed";

export type AgentExecutionState =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "skipped";

export interface OrchestrationSession {
  accepted: OrchestrationRunAccepted | null;
  events: AgentRunEvent[];
  result: OrchestrationResult | null;
  connection: OrchestrationConnection;
  lastSequence: number;
  error: string;
}

export const initialOrchestrationSession: OrchestrationSession = {
  accepted: null,
  events: [],
  result: null,
  connection: "idle",
  lastSequence: 0,
  error: "",
};

export type OrchestrationSessionAction =
  | { type: "starting" }
  | { type: "accepted"; accepted: OrchestrationRunAccepted }
  | { type: "event"; event: AgentRunEvent }
  | { type: "reconnecting" }
  | { type: "completed"; result: OrchestrationResult }
  | { type: "failed"; message: string }
  | { type: "reset" };

export function orchestrationSessionReducer(
  state: OrchestrationSession,
  action: OrchestrationSessionAction,
): OrchestrationSession {
  if (action.type === "reset") {
    return initialOrchestrationSession;
  }
  if (action.type === "starting") {
    return { ...initialOrchestrationSession, connection: "starting" };
  }
  if (action.type === "accepted") {
    return { ...state, accepted: action.accepted, connection: "streaming" };
  }
  if (action.type === "event") {
    const bySequence = new Map(
      [...state.events, action.event].map((item) => [item.sequence, item]),
    );
    const events = [...bySequence.values()].sort(
      (left, right) => left.sequence - right.sequence,
    );
    return {
      ...state,
      events,
      lastSequence: events[events.length - 1]?.sequence ?? 0,
      connection: "streaming",
    };
  }
  if (action.type === "reconnecting") {
    return { ...state, connection: "reconnecting" };
  }
  if (action.type === "completed") {
    return {
      ...state,
      result: action.result,
      connection: "completed",
      error: "",
    };
  }
  return { ...state, connection: "failed", error: action.message };
}

export function deriveAgentStates(
  events: AgentRunEvent[],
): Record<string, AgentExecutionState> {
  const states: Record<string, AgentExecutionState> = {};
  const ordered = [...events].sort(
    (left, right) => left.sequence - right.sequence,
  );
  for (const event of ordered) {
    if (event.type === "started") {
      states[event.agent] = "running";
    } else if (event.type === "completed") {
      states[event.agent] = "completed";
    } else if (event.type === "failed") {
      states[event.agent] = "failed";
    }
  }
  return states;
}
