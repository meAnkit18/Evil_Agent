export type MessageRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  text: string;
  streaming?: boolean;
}

export type HarnessEventType =
  | "connected"
  | "session.status"
  | "text.delta"
  | "text.done"
  | "tool.start"
  | "tool.result"
  | "tool.permission"
  | "session.error"
  | "session.diff";

export interface HarnessEvent {
  type: HarnessEventType;
  sessionID?: string;
  status?: "busy" | "idle" | "error";
  text?: string;
  toolName?: string;
  args?: unknown;
  output?: string;
  durationMs?: number;
  description?: string;
  files?: string[];
  error?: string;
}

export interface ActiveTool {
  name: string;
  args?: unknown;
  startedAt: number;
}
