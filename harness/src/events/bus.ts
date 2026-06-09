export type HarnessEvent =
  | { type: "session.status"; sessionID: string; status: "busy" | "idle" | "error" }
  | { type: "text.delta"; sessionID: string; text: string }
  | { type: "text.done"; sessionID: string }
  | { type: "tool.start"; sessionID: string; toolName: string; args: unknown }
  | { type: "tool.result"; sessionID: string; toolName: string; output: string; durationMs: number }
  | { type: "tool.permission"; sessionID: string; toolName: string; args: unknown; description: string }
  | { type: "session.error"; sessionID: string; error: string }
  | { type: "session.diff"; sessionID: string; files: string[] };

type Listener = (event: HarnessEvent) => void;

const listeners = new Map<string, Set<Listener>>();

export const bus = {
  subscribe(sessionID: string, listener: Listener): () => void {
    if (!listeners.has(sessionID)) listeners.set(sessionID, new Set());
    listeners.get(sessionID)!.add(listener);
    return () => listeners.get(sessionID)?.delete(listener);
  },

  emit(event: HarnessEvent): void {
    const sessionListeners = listeners.get(event.sessionID);
    if (sessionListeners) {
      for (const listener of sessionListeners) {
        try { listener(event); } catch { /* ignore listener errors */ }
      }
    }
  },
};
