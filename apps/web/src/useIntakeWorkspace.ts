import {
  useCallback,
  useEffect,
  useReducer,
  useRef,
  useState,
} from "react";
import * as api from "./api";
import {
  initialIntakeSession,
  intakeSessionReducer,
  type IntakeFiles,
} from "./intakeSession";

export interface UseIntakeWorkspaceOptions {
  onRunAccepted?: (accepted: api.OrchestrationRunAccepted) => void;
}

type CommandName = "create" | "save" | "confirm" | "launch";

export function useIntakeWorkspace(
  options: UseIntakeWorkspaceOptions = {},
) {
  const [isOpen, setIsOpen] = useState(false);
  const [session, dispatch] = useReducer(
    intakeSessionReducer,
    initialIntakeSession,
  );
  const inFlight = useRef<
    Partial<Record<CommandName, Promise<unknown>>>
  >({});
  const commandIds = useRef<Partial<Record<CommandName, string>>>({});
  const onRunAccepted = useRef(options.onRunAccepted);
  onRunAccepted.current = options.onRunAccepted;

  useEffect(() => {
    const statusUrl = session.accepted?.status_url;
    if (!isOpen || statusUrl === undefined) {
      return;
    }
    let active = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let controller: AbortController | null = null;

    const poll = async () => {
      while (active) {
        controller = new AbortController();
        try {
          const intake = await api.fetchIntake(
            statusUrl,
            controller.signal,
          );
          if (!active) {
            return;
          }
          dispatch({ type: "received", intake });
          if (!["uploaded", "extracting"].includes(intake.status)) {
            return;
          }
        } catch (error) {
          if (!active || controller.signal.aborted) {
            return;
          }
          dispatch({ type: "failed", message: errorMessage(error) });
          return;
        }
        await new Promise<void>((resolve) => {
          timer = setTimeout(resolve, 750);
        });
      }
    };

    void poll();
    return () => {
      active = false;
      controller?.abort();
      if (timer !== null) {
        clearTimeout(timer);
      }
    };
  }, [isOpen, session.accepted?.status_url]);

  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);

  const selectFiles = useCallback((files: IntakeFiles) => {
    dispatch({ type: "select-files", files });
  }, []);

  const processFiles = useCallback(async (): Promise<void> => {
    const existing = inFlight.current.create as
      | Promise<void>
      | undefined;
    if (existing !== undefined) {
      return existing;
    }
    const { notice, inventory, shelfPhoto } = session.files;
    if (notice === null || inventory === null) {
      dispatch({
        type: "failed",
        message: "Recall notice and inventory CSV are required.",
      });
      return;
    }
    const requestId = commandId(commandIds.current, "create");
    const pending = (async () => {
      dispatch({ type: "processing" });
      try {
        const accepted = await api.createIntakePacket(
          requestId,
          notice,
          inventory,
          shelfPhoto ?? undefined,
        );
        commandIds.current.create = undefined;
        dispatch({ type: "accepted", accepted });
      } catch (error) {
        dispatch({ type: "failed", message: errorMessage(error) });
      } finally {
        inFlight.current.create = undefined;
      }
    })();
    inFlight.current.create = pending;
    return pending;
  }, [session.files]);

  const editCriteria = useCallback(
    <Field extends keyof api.RecallCriteriaDraft>(
      field: Field,
      value: api.RecallCriteriaDraft[Field],
    ) => {
      dispatch({ type: "edit-criteria", field, value });
    },
    [],
  );

  const saveDraft = useCallback(async (): Promise<void> => {
    const existing = inFlight.current.save as Promise<void> | undefined;
    if (existing !== undefined) {
      return existing;
    }
    if (
      session.view === null ||
      session.criteria === null ||
      session.view.draft === null
    ) {
      return;
    }
    const requestId = commandId(commandIds.current, "save");
    const pending = (async () => {
      dispatch({ type: "operation", operation: "saving" });
      try {
        const intake = await api.updateIntakeDraft(
          session.view!.intake_id,
          {
            request_id: requestId,
            expected_version: session.serverVersion,
            criteria: session.criteria!,
            inventory: session.inventory,
          },
        );
        commandIds.current.save = undefined;
        dispatch({ type: "received", intake });
      } catch (error) {
        dispatch({ type: "failed", message: errorMessage(error) });
      } finally {
        inFlight.current.save = undefined;
      }
    })();
    inFlight.current.save = pending;
    return pending;
  }, [
    session.criteria,
    session.inventory,
    session.serverVersion,
    session.view,
  ]);

  const confirm = useCallback(async (): Promise<api.IntakeView | null> => {
    const existing = inFlight.current.confirm as
      | Promise<api.IntakeView | null>
      | undefined;
    if (existing !== undefined) {
      return existing;
    }
    if (session.view === null) {
      return null;
    }
    const requestId = commandId(commandIds.current, "confirm");
    const pending = (async () => {
      dispatch({ type: "operation", operation: "confirming" });
      try {
        const intake = await api.confirmIntake(session.view!.intake_id, {
          request_id: requestId,
          expected_version: session.serverVersion,
        });
        commandIds.current.confirm = undefined;
        dispatch({ type: "received", intake });
        return intake;
      } catch (error) {
        dispatch({ type: "failed", message: errorMessage(error) });
        return null;
      } finally {
        inFlight.current.confirm = undefined;
      }
    })();
    inFlight.current.confirm = pending;
    return pending;
  }, [session.serverVersion, session.view]);

  const continueToLaunch = useCallback(() => {
    dispatch({ type: "show-launch" });
  }, []);

  const launch = useCallback(async (): Promise<void> => {
    const existing = inFlight.current.launch as Promise<void> | undefined;
    if (existing !== undefined) {
      return existing;
    }
    if (session.view === null) {
      return;
    }
    const pending = (async () => {
      dispatch({ type: "operation", operation: "launching" });
      try {
        let view = session.view!;
        if (view.status === "review_required") {
          const requestId = commandId(commandIds.current, "confirm");
          view = await api.confirmIntake(view.intake_id, {
            request_id: requestId,
            expected_version: session.serverVersion,
          });
          commandIds.current.confirm = undefined;
          dispatch({ type: "received", intake: view });
        }
        if (!["ready", "run_started"].includes(view.status)) {
          throw new Error("Intake must be confirmed before launch.");
        }
        const requestId = commandId(commandIds.current, "launch");
        const accepted = await api.startIntakeRun(
          view.intake_id,
          requestId,
        );
        commandIds.current.launch = undefined;
        dispatch({ type: "received", intake: accepted.intake });
        onRunAccepted.current?.(accepted.run);
        setIsOpen(false);
      } catch (error) {
        dispatch({ type: "failed", message: errorMessage(error) });
      } finally {
        inFlight.current.launch = undefined;
      }
    })();
    inFlight.current.launch = pending;
    return pending;
  }, [session.serverVersion, session.view]);

  const reset = useCallback(() => {
    inFlight.current = {};
    commandIds.current = {};
    dispatch({ type: "reset" });
  }, []);

  const receive = useCallback((intake: api.IntakeView) => {
    dispatch({ type: "received", intake });
  }, []);

  return {
    isOpen,
    session,
    open,
    close,
    selectFiles,
    processFiles,
    editCriteria,
    saveDraft,
    confirm,
    continueToLaunch,
    launch,
    reset,
    receive,
  };
}

function commandId(
  values: Partial<Record<CommandName, string>>,
  command: CommandName,
): string {
  const existing = values[command];
  if (existing !== undefined) {
    return existing;
  }
  const created = crypto.randomUUID();
  values[command] = created;
  return created;
}

function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Incident intake is unavailable.";
}
