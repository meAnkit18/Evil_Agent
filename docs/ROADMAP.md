# Evil Agent — Roadmap

## Phase 1 — Harness Core

Goal: A working HTTP+SSE agent server you can talk to with curl.

### Milestones
- [x] Root monorepo setup (workspaces)
- [ ] `harness/` package init (Bun + TypeScript)
- [ ] `storage/database.ts` — SQLite schema (sessions, messages, parts)
- [ ] `provider/anthropic.ts` — streaming Claude via @anthropic-ai/sdk
- [ ] `tool/` — read, write, edit, glob, grep, bash (6 core tools)
- [ ] `session/processor.ts` — agent loop (stream processor)
- [ ] `session/session.ts` — session CRUD
- [ ] `events/bus.ts` — in-process event bus + SSE hub
- [ ] `server/server.ts` + `routes.ts` — Hono HTTP server

### Acceptance Criteria
```bash
# Start harness
cd harness && bun run src/index.ts

# Create session
curl -X POST localhost:7777/session

# Stream events (terminal 2)
curl -N localhost:7777/session/SESSION_ID/stream

# Send prompt (terminal 3)
curl -X POST localhost:7777/session/SESSION_ID/prompt \
  -H "Content-Type: application/json" \
  -d '{"text": "list files in /tmp and tell me what you find"}'

# → SSE stream shows text.delta events and tool events
```

---

## Phase 2 — Electron Client Integration

Goal: Transparent overlay talks to harness. Type a prompt, see streaming response.

### Milestones
- [ ] Migrate renderer from plain HTML/TS to React + Vite
- [ ] `<ChatArea>` component — message history with user/agent bubbles
- [ ] `<PromptBar>` component — input with auto-grow, Enter to submit
- [ ] `<Sidebar>` component — session list, agent selector, nav
- [ ] `<ToolActivity>` component — strip showing active tool
- [ ] `<PermissionOverlay>` component — ask user before destructive ops
- [ ] `client/src/main.ts` — spawn harness, IPC↔HTTP bridge
- [ ] `client/src/preload.ts` — contextBridge expansion
- [ ] SSE EventSource connected in renderer

### Acceptance Criteria
```
1. npm start in client/ launches transparent overlay
2. Harness auto-spawns in background
3. Type "what files are in my home dir?" in PromptBar
4. See streaming response appear in ChatArea
5. See "bash" tool activity in ToolActivity strip
```

---

## Phase 3 — System Control

Goal: Agent can see and interact with the entire desktop.

### Milestones
- [ ] `tool/screenshot.ts` — capture screen → base64 image → pass to Claude
- [ ] `tool/mouse.ts` — move, click, double-click via @nut-tree/nut-js
- [ ] `tool/keyboard.ts` — type text, press key combos
- [ ] `tool/app_launch.ts` — open apps by name/path
- [ ] Register system tools in `build` agent
- [ ] System prompt updated: agent knows it can see and control the screen
- [ ] Screenshot tool streams image to Claude for visual reasoning

### Acceptance Criteria
```
1. "Take a screenshot and describe what you see"
   → screenshot tool fires, Claude describes the screen
2. "Open a terminal and run ls -la"
   → open_app launches terminal, keyboard types command
3. "Click on the clock in the taskbar"
   → mouse_click tool moves and clicks
```

---

## Phase 4 — MCP + Polish

Goal: Browser control, web search, permission UX, session history.

### Milestones
- [ ] `mcp/client.ts` — MCP client manager (stdio + http transports)
- [ ] Connect Playwright MCP (browser navigation, click, fill)
- [ ] Connect Brave Search MCP (web search)
- [ ] Permission dialog wired to `tool.permission` SSE events
- [ ] Session history list in Sidebar (resume past sessions)
- [ ] Agent mode selector in Sidebar (build / plan / explore)
- [ ] Settings panel: API key input, model selector
- [ ] Keyboard shortcut overlay (Ctrl+/ to show all shortcuts)

### Acceptance Criteria
```
1. "Search the web for latest AI news and summarize"
   → Brave search MCP fires, results summarized
2. "Open chrome, go to github.com, and star the first repo you see"
   → Playwright MCP navigates, clicks
3. Agent asks "This will delete a file. Allow?" before rm commands
4. Sidebar shows previous sessions, clicking one restores history
```

---

## Future / Stretch

- **Voice input**: whisper.cpp integration for voice-to-text prompt
- **Multi-monitor**: screenshot supports monitor index selection
- **Agent memory**: persistent vector store of past actions/learnings
- **Plugin system**: load custom tools from npm packages
- **Remote mode**: harness runs on a server, client connects remotely
- **Slack/GitHub integration**: agent responds to Slack messages or GitHub issues
