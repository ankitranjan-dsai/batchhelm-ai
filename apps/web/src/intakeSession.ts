import type {
  IntakeAccepted,
  IntakeView,
  InventoryItem,
  RecallCriteriaDraft,
} from "./api";

export type IntakeStage = "files" | "processing" | "review" | "launch";
export type IntakeOperation =
  | "idle"
  | "uploading"
  | "saving"
  | "confirming"
  | "launching";

export interface IntakeFiles {
  notice: File | null;
  inventory: File | null;
  shelfPhoto: File | null;
}

export interface IntakeSession {
  stage: IntakeStage;
  files: IntakeFiles;
  accepted: IntakeAccepted | null;
  view: IntakeView | null;
  criteria: RecallCriteriaDraft | null;
  inventory: InventoryItem[];
  serverVersion: number;
  dirtyFields: string[];
  operation: IntakeOperation;
  error: string;
}

const emptyFiles: IntakeFiles = {
  notice: null,
  inventory: null,
  shelfPhoto: null,
};

export const initialIntakeSession: IntakeSession = {
  stage: "files",
  files: emptyFiles,
  accepted: null,
  view: null,
  criteria: null,
  inventory: [],
  serverVersion: -1,
  dirtyFields: [],
  operation: "idle",
  error: "",
};

export type IntakeSessionAction =
  | { type: "select-files"; files: IntakeFiles }
  | { type: "processing" }
  | { type: "accepted"; accepted: IntakeAccepted }
  | { type: "received"; intake: IntakeView }
  | {
      type: "edit-criteria";
      field: keyof RecallCriteriaDraft;
      value: RecallCriteriaDraft[keyof RecallCriteriaDraft];
    }
  | { type: "operation"; operation: IntakeOperation }
  | { type: "show-launch" }
  | { type: "failed"; message: string }
  | { type: "reset" };

export function intakeSessionReducer(
  state: IntakeSession,
  action: IntakeSessionAction,
): IntakeSession {
  if (action.type === "reset") {
    return initialIntakeSession;
  }
  if (action.type === "select-files") {
    return { ...state, files: action.files, error: "" };
  }
  if (action.type === "processing") {
    return {
      ...state,
      stage: "processing",
      operation: "uploading",
      error: "",
    };
  }
  if (action.type === "accepted") {
    return {
      ...state,
      accepted: action.accepted,
      stage: "processing",
      operation: "idle",
    };
  }
  if (action.type === "received") {
    if (action.intake.version < state.serverVersion) {
      return state;
    }
    const preserveEdits =
      action.intake.version === state.serverVersion &&
      state.dirtyFields.length > 0;
    const draft = action.intake.draft;
    return {
      ...state,
      view: action.intake,
      criteria: preserveEdits
        ? state.criteria
        : (draft?.criteria ?? state.criteria),
      inventory: preserveEdits
        ? state.inventory
        : (draft?.inventory ?? state.inventory),
      serverVersion: action.intake.version,
      dirtyFields: preserveEdits ? state.dirtyFields : [],
      stage: stageFor(action.intake, state.stage),
      operation: "idle",
      error:
        action.intake.status === "failed"
          ? (action.intake.error_message ?? "Intake processing failed.")
          : "",
    };
  }
  if (action.type === "edit-criteria") {
    if (state.criteria === null) {
      return state;
    }
    const path = `criteria.${action.field}`;
    return {
      ...state,
      criteria: {
        ...state.criteria,
        [action.field]: action.value,
      },
      dirtyFields: state.dirtyFields.includes(path)
        ? state.dirtyFields
        : [...state.dirtyFields, path],
      error: "",
    };
  }
  if (action.type === "operation") {
    return { ...state, operation: action.operation, error: "" };
  }
  if (action.type === "show-launch") {
    return { ...state, stage: "launch", error: "" };
  }
  return { ...state, operation: "idle", error: action.message };
}

function stageFor(
  intake: IntakeView,
  current: IntakeStage,
): IntakeStage {
  if (intake.status === "review_required") {
    return current === "launch" ? "launch" : "review";
  }
  if (intake.status === "ready" || intake.status === "run_started") {
    return "launch";
  }
  return "processing";
}
