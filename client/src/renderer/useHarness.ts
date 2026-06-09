import { useState, useEffect, useRef, useCallback } from "react";
import type { ChatMessage, HarnessEvent, ActiveTool } from "./types";

const HARNESS_URL = "http://127.0.0.1:7777";

function genId(): string {
  return Math.random().toString(36).slice(2);
}

export function useHarness() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<"idle" | "busy" | "error">("idle");
  const [activeTool, setActiveTool] = useState<ActiveTool | null>(null);
  const [pendingPermission, setPendingPermission] = useState<{
    toolName: string;
    args: unknown;
    description: string;
  } | null>(null);
  const [connected, setConnected] = useState(false);

  const streamingMsgId = useRef<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  // Create session and subscribe to SSE stream
  useEffect(() => {
    let cancelled = false;

    async function init() {
      // Poll until harness is ready
      for (let i = 0; i < 30; i++) {
        try {
          const r = await fetch(`${HARNESS_URL}/health`);
          if (r.ok) break;
        } catch {
          await new Promise((res) => setTimeout(res, 1000));
        }
      }
      if (cancelled) return;

      // Create session
      const res = await fetch(`${HARNESS_URL}/session`, { method: "POST" });
      const session = await res.json();
      if (cancelled) return;

      setSessionId(session.id);

      // Subscribe to SSE
      const es = new EventSource(`${HARNESS_URL}/session/${session.id}/stream`);
      esRef.current = es;

      es.onopen = () => setConnected(true);
      es.onerror = () => setConnected(false);

      es.onmessage = (e: MessageEvent) => {
        let event: HarnessEvent;
        try { event = JSON.parse(e.data); } catch { return; }

        if (event.type === "connected") {
          setConnected(true);
        }

        if (event.type === "session.status") {
          setStatus(event.status ?? "idle");
          if (event.status === "idle") {
            setActiveTool(null);
            streamingMsgId.current = null;
          }
        }

        if (event.type === "text.delta" && event.text) {
          setMessages((prev) => {
            const id = streamingMsgId.current;
            if (id) {
              return prev.map((m) =>
                m.id === id ? { ...m, text: m.text + event.text!, streaming: true } : m
              );
            }
            const newId = genId();
            streamingMsgId.current = newId;
            return [...prev, { id: newId, role: "assistant", text: event.text!, streaming: true }];
          });
        }

        if (event.type === "text.done") {
          if (streamingMsgId.current) {
            const id = streamingMsgId.current;
            setMessages((prev) =>
              prev.map((m) => (m.id === id ? { ...m, streaming: false } : m))
            );
            streamingMsgId.current = null;
          }
        }

        if (event.type === "tool.start") {
          setActiveTool({
            name: event.toolName ?? "tool",
            args: event.args,
            startedAt: Date.now(),
          });
        }

        if (event.type === "tool.result") {
          setActiveTool(null);
        }

        if (event.type === "tool.permission") {
          setPendingPermission({
            toolName: event.toolName ?? "tool",
            args: event.args,
            description: event.description ?? "",
          });
        }

        if (event.type === "session.error") {
          setMessages((prev) => [
            ...prev,
            { id: genId(), role: "assistant", text: `Error: ${event.error}` },
          ]);
          setStatus("error");
          setActiveTool(null);
        }
      };
    }

    init().catch(console.error);
    return () => {
      cancelled = true;
      esRef.current?.close();
    };
  }, []);

  const sendPrompt = useCallback(
    async (text: string) => {
      if (!sessionId || !text.trim()) return;

      setMessages((prev) => [
        ...prev,
        { id: genId(), role: "user", text: text.trim() },
      ]);

      await fetch(`${HARNESS_URL}/session/${sessionId}/prompt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.trim() }),
      });
    },
    [sessionId]
  );

  const interrupt = useCallback(async () => {
    if (!sessionId) return;
    await fetch(`${HARNESS_URL}/session/${sessionId}/interrupt`, { method: "POST" });
  }, [sessionId]);

  const grantPermission = useCallback(
    async (allow: boolean) => {
      if (!sessionId) return;
      setPendingPermission(null);
      await fetch(`${HARNESS_URL}/session/${sessionId}/permission`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ allow }),
      });
    },
    [sessionId]
  );

  return {
    connected,
    status,
    messages,
    activeTool,
    pendingPermission,
    sendPrompt,
    interrupt,
    grantPermission,
  };
}
