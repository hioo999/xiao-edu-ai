export type TaskState = "pending" | "queued" | "running" | "succeeded" | "failed" | "retrying";

export interface GenerationTask {
  id: string;
  state: TaskState;
  errorCode?: string;
}
