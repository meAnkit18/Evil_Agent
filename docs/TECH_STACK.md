# Evil Agent — Tech Stack

## Runtime & Build

| Tool | Version | Why |
|------|---------|-----|
| **Bun** | ^1.3 | Harness runtime. Built-in SQLite, fast TS execution, native fetch, no transpile step. |
| **Node.js** | ^20 | Electron runtime requirement. Client build only. |
| **TypeScript** | ^5.4 | Shared language across client + harness. Strict mode everywhere. |
| **Vite** | ^5 | Client renderer bundler. Fast HMR for development, optimized prod build for Electron. |

## Client (Electron)

| Package | Why |
|---------|-----|
| **electron** ^30 | Desktop app shell. Transparent frameless window, always-on-top, system tray. |
| **react** ^18 | Component model for chat UI. State management via hooks. |
| **react-dom** ^18 | DOM renderer for React. |
| **@vitejs/plugin-react** | Vite + React integration (fast refresh, JSX transform). |

## Harness

| Package | Why |
|---------|-----|
| **hono** ^4 | Lightweight HTTP framework. Built-in SSE support, fast routing, minimal overhead. |
| **@anthropic-ai/sdk** ^0.30 | Official Anthropic SDK. Streaming tool use, vision (for screenshot), models. |
| **ai** (Vercel AI SDK) ^4 | Multi-provider abstraction. Easy to add OpenAI/Gemini later. |
| **@ai-sdk/anthropic** ^1 | Vercel AI SDK Anthropic adapter. |
| **@modelcontextprotocol/sdk** ^1 | MCP client. Connects to stdio/HTTP MCP servers. |
| **zod** ^3 | Schema validation for tool inputs, API request bodies. |
| **fast-glob** ^3 | File pattern matching for the `glob` tool. |
| **screenshot-desktop** ^1 | Cross-platform screen capture. Returns PNG buffer. |
| **@nut-tree/nut-js** ^4 | Mouse/keyboard automation. Cross-platform (Linux/Mac/Windows). |
| **open** ^10 | Launch applications by name or path. Cross-platform. |
| **bun:sqlite** (built-in) | Zero-install SQLite. Bundled with Bun. Session/message persistence. |

## Why These Choices Over Alternatives

### Bun over Node.js for harness
- Built-in SQLite (`bun:sqlite`) = no `better-sqlite3` native module headaches
- Runs TypeScript directly = no tsc watch + separate runner
- ~3x faster startup than Node for short-lived tool scripts

### Hono over Express / Fastify
- First-class SSE support (`streamSSE`)
- ~10x faster than Express in benchmarks
- Tiny bundle, zero overhead dependencies

### @anthropic-ai/sdk over raw fetch
- Typed streaming events, automatic retry, token counting
- Vision support (pass screenshot as image content)
- Tool use schema generation from JSON Schema

### @nut-tree/nut-js over robotjs
- Actively maintained (robotjs is largely abandoned)
- TypeScript-native, async API
- Better Linux/Wayland support

### React + Vite over plain HTML/TS
- Component model makes chat bubbles, tool states, and overlays composable
- React state = no manual DOM manipulation
- Vite = instant HMR during development

## Environment Variables

```bash
# harness/.env
ANTHROPIC_API_KEY=sk-ant-...
HARNESS_PORT=7777              # default
DEFAULT_MODEL=claude-opus-4-8  # or claude-sonnet-4-6

# Optional MCP
BRAVE_API_KEY=...
```
