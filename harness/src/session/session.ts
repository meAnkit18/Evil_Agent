import { db, newId, now } from "../storage/database.ts";
import type { Message } from "../provider/provider.ts";

export interface Session {
  id: string;
  agent: string;
  model: string;
  title: string | null;
  created_at: number;
  updated_at: number;
}

export const sessionStore = {
  create(opts: { agent?: string; model?: string }): Session {
    const session: Session = {
      id: newId(),
      agent: opts.agent ?? "build",
      model: opts.model ?? (process.env.DEFAULT_MODEL ?? "claude-opus-4-8"),
      title: null,
      created_at: now(),
      updated_at: now(),
    };
    db.run(
      "INSERT INTO sessions (id, agent, model, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
      [session.id, session.agent, session.model, session.title, session.created_at, session.updated_at]
    );
    return session;
  },

  get(id: string): Session | null {
    return db.query("SELECT * FROM sessions WHERE id = ?").get(id) as Session | null;
  },

  list(): Session[] {
    return db.query("SELECT * FROM sessions ORDER BY created_at DESC").all() as Session[];
  },

  updateTitle(id: string, title: string) {
    db.run("UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?", [title, now(), id]);
  },

  saveMessage(sessionId: string, role: "user" | "assistant", content: Message["content"]) {
    db.run(
      "INSERT INTO messages (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
      [newId(), sessionId, role, JSON.stringify(content), now()]
    );
    db.run("UPDATE sessions SET updated_at = ? WHERE id = ?", [now(), sessionId]);
  },

  getMessages(sessionId: string): Message[] {
    const rows = db
      .query("SELECT role, content FROM messages WHERE session_id = ? ORDER BY created_at ASC")
      .all(sessionId) as Array<{ role: string; content: string }>;

    return rows.map((r) => ({
      role: r.role as "user" | "assistant",
      content: JSON.parse(r.content),
    }));
  },
};
