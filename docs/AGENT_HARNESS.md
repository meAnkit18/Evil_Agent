# Evil Agent — Harness Internals

## HTTP API Reference

Base URL: `http://localhost:7777`

### Sessions

```
POST   /session                    Create new session
GET    /session                    List all sessions
GET    /session/:id                Get session + message history
POST   /session/:id/prompt         Send user message → begins agent loop
POST   /session/:id/interrupt      Stop current generation
POST   /session/:id/permission     Grant or deny pending tool permission
GET    /session/:id/stream         SSE event stream (keep-alive)
```

**POST /session** — request: `{ agent?: string, model?: string }` → response: `{ id, agent, model, createdAt }`

**POST /session/:id/prompt** — request: `{ text: string, files?: string[] }` → response: `{ ok: true }`

**POST /session/:id/permission** — request: `{ allow: boolean }` → response: `{ ok: true }`

### Info

```
GET    /health                     Liveness check → { ok: true }
GET    /tool                       List tools → Tool[]
GET    /agent                      List agents → AgentInfo[]
GET    /mcp                        MCP server status → McpStatus[]
```

---

## SSE Event Reference

Connect: `GET /session/:id/stream`  
Content-Type: `text/event-stream`

```typescript
type HarnessEvent =
  | { type: "session.status";   sessionID: string; status: "busy" | "idle" | "error" }
  | { type: "text.delta";       sessionID: string; text: string }
  | { type: "text.done";        sessionID: string }
  | { type: "tool.start";       sessionID: string; toolName: string; args: unknown }
  | { type: "tool.result";      sessionID: string; toolName: string; output: string; durationMs: number }
  | { type: "tool.permission";  sessionID: string; toolName: string; args: unknown; description: string }
  | { type: "session.error";    sessionID: string; error: string }
  | { type: "session.diff";     sessionID: string; files: string[] }
```

---

## Session State Machine

```
IDLE ──(user sends prompt)──► BUSY
BUSY ──(generation done)────► IDLE
BUSY ──(error)──────────────► ERROR
BUSY ──(interrupt)──────────► IDLE
ERROR ──(new prompt)────────► BUSY
```

---

## Agent Loop (processor.ts)

The agent loop in `session/processor.ts` is the core of the harness.

```
runAgentLoop(session, userPrompt, emit)
  1. Load message history from SQLite
  2. Append user message, save to SQLite
  3. emit session.status = busy
  4. LOOP:
     a. Call provider.stream({ messages, tools })
     b. For each streaming event:
        - text-delta → emit text.delta
        - tool-call  → execute tool, emit tool.start / tool.result
        - finish     → break inner loop
     c. If tool calls were made → append results, go to 4a
     d. If no tool calls → break outer loop
  5. emit text.done
  6. emit session.status = idle
```

### Doom Loop Prevention
If the same tool is called with identical args 3 times in a row, the loop stops and returns an error to prevent infinite loops.

### Context Compaction
When the message history exceeds ~80% of the model's context window, the processor summarizes the middle of the conversation and replaces it with a compact summary, then continues.

---

## Tool Interface

Every tool implements:

```typescript
interface ToolDef {
  name: string
  description: string          // Shown to LLM in system prompt / tool list
  parameters: z.ZodSchema      // Validated before execute() is called
  execute(args: unknown, ctx: ToolContext): Promise<ToolResult>
  permission?: PermissionLevel // "auto" | "ask_once" | "ask_always"
}

interface ToolContext {
  sessionID: string
  workingDir: string
  signal: AbortSignal
  emit: Emitter
}

interface ToolResult {
  output: string               // Text returned to LLM
  metadata?: Record<string, unknown>
  files?: string[]             // Paths of created/modified files
}
```

---

## Agent Definitions

Agents are defined in `agent/agents.ts`:

| Agent | Tools Allowed | Use Case |
|-------|--------------|----------|
| `build` | all tools | Default — executes tasks end-to-end |
| `plan` | read, glob, grep, screenshot | Plans without executing; read-only |
| `explore` | read, glob, grep, screenshot | Observe and report only |

The agent is selected per-session and stored in SQLite. The tool registry filters available tools based on the current agent.

---

## Permission Model

```
auto        → executes without asking (read, glob, grep, screenshot, mouse_move)
ask_once    → asks first time per session, then auto-allows (bash, write, edit, open_app)
ask_always  → always asks before executing (destructive key combos, mouse_click on system UI)
```

When a tool needs permission, the harness:
1. Emits `tool.permission` event over SSE
2. Pauses execution
3. Waits for `POST /session/:id/permission` with `{ allow: boolean }`
4. Continues or cancels

---

## SQLite Schema

```sql
CREATE TABLE sessions (
  id          TEXT PRIMARY KEY,
  agent       TEXT NOT NULL DEFAULT 'build',
  model       TEXT NOT NULL,
  title       TEXT,
  created_at  INTEGER NOT NULL,
  updated_at  INTEGER NOT NULL
);

CREATE TABLE messages (
  id          TEXT PRIMARY KEY,
  session_id  TEXT NOT NULL REFERENCES sessions(id),
  role        TEXT NOT NULL,   -- 'user' | 'assistant' | 'tool'
  content     TEXT NOT NULL,   -- JSON stringified
  created_at  INTEGER NOT NULL
);
```

---

## Environment

```
ANTHROPIC_API_KEY    (required) Claude API key
HARNESS_PORT         (default: 7777) HTTP server port
DEFAULT_MODEL        (default: claude-opus-4-8) Model ID
DATA_DIR             (default: ~/.evil-agent) SQLite database location
```
