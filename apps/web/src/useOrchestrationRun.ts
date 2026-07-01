import { useCallback, useEffect, useReducer, useState } from "react";
import {
  orchestrationEventsUrl,
  startDemoRun,
  type AgentRunEvent,
  type OrchestrationResult,
  type OrchestrationRunAccepted,
} from "./api";
import {
  initialOrchestrationSession,
  orchestrationSessionReducer,
} from "./orchestrationSession";

export const ORCHESTRATION_SESSION_KEY = "batchhelm.orchestration.run";
const ORCHESTRATION_REQUEST_KEY = "batchhelm.orchestration.request";
const pendingStarts = new Map<
  string,
  Promise<OrchestrationRunAccepted>
>();

const EVENT_TYPES = [
  "started",
  "reasoning",
  "output",
  "completed",
  "failed",
  "retry",
  "conflict",
  "resolved",
  "checkpoint",
  "orchestrator",
] as const;

export function useOrchestrationRun() {
  const [generation, setGeneration] = useState(0);
  const [session, dispatch] = useReducer(
    orchestrationSessionReducer,
    initialOrchestrationSession,
  );

  useEffect(() => {
    let active = true;
    let source: EventSource | null = null;
    let settled = false;
    dispatch({ type: "starting" });

    const connect = (accepted: OrchestrationRunAccepted) => {
      if (!active) {
        return;
      }
      sessionStorage.setItem(
        ORCHESTRATION_SESSION_KEY,
        JSON.stringify(accepted),
      );
      dispatch({ type: "accepted", accepted });
      source = new EventSource(orchestrationEventsUrl(accepted));

      for (const type of EVENT_TYPES) {
        source.addEventListener(type, (message) => {
          const event = JSON.parse(
            (message as MessageEvent<string>).data,
          ) as AgentRunEvent;
          dispatch({ type: "event", event });
        });
      }

      source.addEventListener("result", (message) => {
        settled = true;
        dispatch({
          type: "completed",
          result: JSON.parse(
            (message as MessageEvent<string>).data,
          ) as OrchestrationResult,
        });
        source?.close();
      });

      source.addEventListener("run-error", (message) => {
        settled = true;
        const payload = JSON.parse(
          (message as MessageEvent<string>).data,
        ) as { message?: string };
        dispatch({
          type: "failed",
          message: payload.message ?? "The orchestration run failed.",
        });
        source?.close();
      });

      source.onerror = () => {
        if (!settled) {
          dispatch({ type: "reconnecting" });
        }
      };
    };

    const restored = restoreAcceptedRun();
    if (restored !== null) {
      connect(restored);
    } else {
      void startRunOnce()
        .then(connect)
        .catch(() => {
          if (active) {
            dispatch({
              type: "failed",
              message: "Agent Mission Control is unavailable.",
            });
          }
        });
    }

    return () => {
      active = false;
      source?.close();
    };
  }, [generation]);

  const rerun = useCallback(() => {
    sessionStorage.removeItem(ORCHESTRATION_SESSION_KEY);
    sessionStorage.removeItem(ORCHESTRATION_REQUEST_KEY);
    dispatch({ type: "reset" });
    setGeneration((value) => value + 1);
  }, []);

  return { session, rerun };
}

function startRunOnce(): Promise<OrchestrationRunAccepted> {
  let requestId = sessionStorage.getItem(ORCHESTRATION_REQUEST_KEY);
  if (requestId === null) {
    requestId = crypto.randomUUID();
    sessionStorage.setItem(ORCHESTRATION_REQUEST_KEY, requestId);
  }

  const existing = pendingStarts.get(requestId);
  if (existing !== undefined) {
    return existing;
  }

  const pending = startDemoRun(requestId)
    .then((accepted) => {
      if (sessionStorage.getItem(ORCHESTRATION_REQUEST_KEY) === requestId) {
        sessionStorage.setItem(
          ORCHESTRATION_SESSION_KEY,
          JSON.stringify(accepted),
        );
        sessionStorage.removeItem(ORCHESTRATION_REQUEST_KEY);
      }
      return accepted;
    })
    .catch((error: unknown) => {
      if (sessionStorage.getItem(ORCHESTRATION_REQUEST_KEY) === requestId) {
        sessionStorage.removeItem(ORCHESTRATION_REQUEST_KEY);
      }
      throw error;
    })
    .finally(() => {
      pendingStarts.delete(requestId);
    });
  pendingStarts.set(requestId, pending);
  return pending;
}

function restoreAcceptedRun(): OrchestrationRunAccepted | null {
  const raw = sessionStorage.getItem(ORCHESTRATION_SESSION_KEY);
  if (raw === null) {
    return null;
  }
  try {
    const value = JSON.parse(raw) as Partial<OrchestrationRunAccepted>;
    if (
      typeof value.run_id !== "string" ||
      typeof value.incident_id !== "string" ||
      typeof value.events_url !== "string" ||
      typeof value.result_url !== "string"
    ) {
      sessionStorage.removeItem(ORCHESTRATION_SESSION_KEY);
      return null;
    }
    return value as OrchestrationRunAccepted;
  } catch {
    sessionStorage.removeItem(ORCHESTRATION_SESSION_KEY);
    return null;
  }
}
