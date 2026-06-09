# Evil Agent — Architecture

## System Overview

Evil Agent is a desktop AI agent that controls the user's PC via a transparent always-on-top Electron overlay. The user types natural language prompts; the AI executes tools (file ops, shell, mouse, keyboard, screen capture, browser) to accomplish tasks autonomously.

```
┌──────────────────────────────────────────────────────────────┐
│  Electron Client  (transparent fullscreen overlay)           │
│                                                              │
│  ┌──────────────────┐  ┌────────────────────────────────┐   │
│  │   Sidebar        │  │  Chat Area                     │   │
│  │  (nav + history) │  │  user bubbles + agent bubbles  │   │
│  └──────────────────┘  │  tool activity strip           │   │
│  ┌─────────────────────┴──────────────────────────────┐  │   │
│  │  Prompt Bar  (bottom — user input)                 │  │   │
│  └────────────────────────────────────────────────────┘  │   │
└──────────────────────────────┬───────────────────────────────┘
                               │ HTTP + SSE  (localhost:7777)
                               │ IPC bridge (Electron main↔renderer)
                               ↓
┌──────────────────────────────────────────────────────────────┐
│  Agent Harness  (Bun process)                                │
│                                                              │
│  ┌─────────────────┐  ┌────────────────┐  ┌─────────────┐  │
│  │  HTTP Server    │  │  Session Layer │  │  Event Bus  │  │
│  │  (Hono)         │  │  processor.ts  │  │  SSE hub    │  │
│  │  routes.ts      │  │  session.ts    │  │  bus.ts     │  │
│  └────────┬────────┘  └───────┬────────┘  └──────┬──────┘  │
│           │                   │                   │         │
│  ┌────────▼───────────────────▼───────────────────▼──────┐  │
│  │                    Tool Registry                       │  │
│  │  read · write · edit · glob · grep · bash             │  │
│  │  screenshot · mouse · keyboard · open_app             │  │
│  └────────────────────┬───────────────────────────────────┘  │
│                       │                                      │
│  ┌────────────────────▼───────────────────────────────────┐  │
│  │  Provider Layer  (Anthropic / AI SDK)                  │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  SQLite Storage  (bun:sqlite)                        │    │
│  │  sessions · messages · parts                         │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────────┬───────────────────────────────┘
                               │ stdio / HTTP
                               ↓
                    ┌──────────────────────┐
                    │  MCP Servers         │
                    │  - filesystem        │
                    │  - brave-search      │
                    │  - playwright        │
                    └──────────────────────┘
```

## Component Responsibilities

| Component | Package | Responsibility |
|-----------|---------|----------------|
| Electron main | `client/src/main.ts` | Spawn harness, manage lifecycle, IPC↔HTTP bridge |
| Preload | `client/src/preload.ts` | Secure contextBridge API surface to renderer |
| React UI | `client/src/renderer/` | Chat display, prompt input, tool activity, permissions |
| HTTP Server | `harness/src/server/` | REST API + SSE event stream over localhost:7777 |
| Session Processor | `harness/src/session/processor.ts` | **Core agent loop** — drives LLM stream, executes tools |
| Session Store | `harness/src/session/session.ts` | CRUD sessions/messages in SQLite |
| Tool Registry | `harness/src/tool/registry.ts` | Register, filter, and execute tools |
| Provider | `harness/src/provider/` | Abstraction over Anthropic / AI SDK |
| MCP Client | `harness/src/mcp/client.ts` | Connect to MCP servers, surface as tools |
| Storage | `harness/src/storage/database.ts` | SQLite schema + query helpers |
| Event Bus | `harness/src/events/bus.ts` | In-process pub/sub + SSE broadcasting |

## Data Flow — User Prompt to Response

```
1. User types prompt in PromptBar
2. renderer calls window.electronAPI.sendPrompt(sessionID, text)
3. IPC → main.ts → POST http://localhost:7777/session/:id/prompt
4. Harness: session.addMessage('user', text) → SQLite
5. Harness: processor.run(session, text)
6.   → provider.stream({ messages, tools })        ← LLM generates
7.   → for each LLMEvent in stream:
8.       text-delta  → bus.emit('text.delta')       ← SSE to client
9.       tool-call   → toolRegistry.execute()       ← tool runs
10.               → bus.emit('tool.start/result')   ← SSE to client
11.      loop: append tool results, call LLM again
12.  finish → bus.emit('session.status', 'idle')
13. Renderer: EventSource receives SSE events → React state updates
```

## Communication Protocols

### Electron IPC (main ↔ renderer)
- `harness:create-session` → `{ sessionID }`
- `harness:send-prompt` → fires and returns `{ ok }`
- `harness:interrupt` → cancels current generation
- `harness:grant-permission` → approve/deny tool permission

### HTTP API (localhost:7777)
See [AGENT_HARNESS.md](./AGENT_HARNESS.md) for full route reference.

### SSE Stream
The renderer opens a direct `EventSource` connection to `GET /session/:id/stream`.
Events push updates in real time without polling.

## Key Design Decisions

- **Separate process**: Harness is a Bun child process. The UI can crash/reload without losing agent state.
- **HTTP+SSE not IPC**: Harness can be tested with curl independent of Electron. Future: web UI or mobile client connects to same API.
- **Plain async/await**: No Effect-TS. Standard TypeScript that anyone can read and contribute to.
- **bun:sqlite**: Zero-dependency, fast, built into Bun. No ORM overhead.
- **Streaming-first**: Every token and tool event streams to the UI in real time.
