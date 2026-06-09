import { Hono } from "hono";
import { stream } from "hono/streaming";
import { sessionStore } from "../session/session.ts";
import { runAgentLoop, interruptSession } from "../session/processor.ts";
import { bus } from "../events/bus.ts";
import { toolRegistry } from "../tool/registry.ts";
import { listAgents } from "../agent/agents.ts";
import type { HarnessEvent } from "../events/bus.ts";

const DEFAULT_WORKING_DIR = process.env.HOME ?? "/tmp";

export function createRoutes(): Hono {
  const app = new Hono();

  // Health check
  app.get("/health", (c) => c.json({ ok: true, ts: Date.now() }));

  // ─── Sessions ────────────────────────────────────────────────────────────

  app.post("/session", async (c) => {
    const body = await c.req.json().catch(() => ({}));
    const session = sessionStore.create({
      agent: body.agent,
      model: body.model,
    });
    return c.json(session);
  });

  app.get("/session", (c) => {
    return c.json(sessionStore.list());
  });

  app.get("/session/:id", (c) => {
    const session = sessionStore.get(c.req.param("id"));
    if (!session) return c.json({ error: "Not found" }, 404);
    const messages = sessionStore.getMessages(session.id);
    return c.json({ ...session, messages });
  });

  app.post("/session/:id/prompt", async (c) => {
    const session = sessionStore.get(c.req.param("id"));
    if (!session) return c.json({ error: "Not found" }, 404);

    const body = await c.req.json().catch(() => ({}));
    const text = body.text as string;
    if (!text?.trim()) return c.json({ error: "text required" }, 400);

    const workingDir = body.cwd ?? DEFAULT_WORKING_DIR;

    // Run agent loop in background (don't await)
    runAgentLoop(session.id, text.trim(), workingDir).catch((err) => {
      bus.emit({ type: "session.error", sessionID: session.id, error: String(err) });
    });

    return c.json({ ok: true });
  });

  app.post("/session/:id/interrupt", (c) => {
    interruptSession(c.req.param("id"));
    return c.json({ ok: true });
  });

  // SSE stream
  app.get("/session/:id/stream", (c) => {
    const sessionId = c.req.param("id");

    c.header("Content-Type", "text/event-stream");
    c.header("Cache-Control", "no-cache");
    c.header("Connection", "keep-alive");
    c.header("Access-Control-Allow-Origin", "*");

    return stream(c, async (s) => {
      let closed = false;

      const send = (event: HarnessEvent) => {
        if (closed) return;
        s.write(`data: ${JSON.stringify(event)}\n\n`).catch(() => {
          closed = true;
        });
      };

      // Send a ping to confirm connection
      await s.write(`data: ${JSON.stringify({ type: "connected", sessionID: sessionId })}\n\n`);

      const unsubscribe = bus.subscribe(sessionId, send);

      // Keep alive ping every 15s
      const pingInterval = setInterval(() => {
        if (closed) { clearInterval(pingInterval); return; }
        s.write(": ping\n\n").catch(() => { closed = true; });
      }, 15_000);

      // Wait until client disconnects
      await new Promise<void>((resolve) => {
        s.onAbort(() => { closed = true; resolve(); });
      });

      clearInterval(pingInterval);
      unsubscribe();
    });
  });

  // ─── Info ─────────────────────────────────────────────────────────────────

  app.get("/tool", (c) => {
    return c.json(
      toolRegistry.getAll().map((t) => ({
        name: t.name,
        description: t.description,
        permission: t.permission ?? "ask_once",
      }))
    );
  });

  app.get("/agent", (c) => {
    return c.json(listAgents());
  });

  app.get("/mcp", (c) => {
    return c.json({ servers: [], status: "not_configured" });
  });

  return app;
}
