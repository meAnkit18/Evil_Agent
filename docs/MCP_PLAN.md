# Evil Agent — MCP Integration Plan

## What is MCP?

Model Context Protocol (MCP) is a standard for connecting AI agents to external tool servers. Each MCP server exposes tools that the agent can call, just like built-in tools. The harness connects as an MCP client; servers run as separate processes.

---

## Phase 4 MCP Servers

### 1. Filesystem (official)
```jsonc
// harness/.mcp.json
{
  "filesystem": {
    "type": "stdio",
    "command": "npx @modelcontextprotocol/server-filesystem /home"
  }
}
```
**Tools provided:** `read_file`, `write_file`, `list_directory`, `search_files`
**Why:** Enhanced filesystem access with directory tree listing, used to supplement built-in file tools.

### 2. Brave Search (official)
```jsonc
{
  "brave-search": {
    "type": "stdio",
    "command": "npx @modelcontextprotocol/server-brave-search",
    "env": { "BRAVE_API_KEY": "$BRAVE_API_KEY" }
  }
}
```
**Tools provided:** `brave_web_search`, `brave_local_search`
**Why:** Web search without needing browser automation. Fast for information retrieval tasks.

### 3. Playwright (browser automation)
```jsonc
{
  "playwright": {
    "type": "stdio",
    "command": "npx @playwright/mcp"
  }
}
```
**Tools provided:** `navigate`, `click`, `fill`, `screenshot`, `get_text`, `select`, `evaluate`
**Why:** Full browser control. Agent can open URLs, fill forms, extract content, automate web tasks.

### 4. Custom: system-info (planned)
```jsonc
{
  "system-info": {
    "type": "stdio",
    "command": "bun run mcp-servers/system-info/src/index.ts"
  }
}
```
**Tools provided (planned):** `list_processes`, `get_window_list`, `focus_window`, `get_active_window`
**Why:** Get running processes + window list so agent can target specific windows for GUI automation.

---

## MCP Client Architecture (harness/src/mcp/client.ts)

```typescript
// Config loaded from harness/.mcp.json
// Servers start on demand (lazy init)
// Tools auto-registered in ToolRegistry with prefix: "mcp_<server>_<toolname>"

class McpClientManager {
  async connect(name: string, config: McpServerConfig): Promise<void>
  async getTools(): Promise<ToolDef[]>
  async callTool(name: string, args: unknown): Promise<ToolResult>
  getStatus(): McpStatus[]
}
```

---

## Tool Naming Convention

MCP tools are prefixed to avoid collisions with built-in tools:
- `mcp_playwright_navigate`
- `mcp_brave-search_brave_web_search`
- `mcp_filesystem_read_file`

---

## Config File Location

`harness/.mcp.json` — defines which MCP servers to load.  
Env vars referenced with `$VAR_NAME` are interpolated from the harness process env.

---

## Adding a New MCP Server

1. Add entry to `harness/.mcp.json`
2. Restart harness (or: future hot-reload via `POST /mcp/reload`)
3. Tools appear automatically in `GET /tool` response
4. Agent can call them immediately

No code changes needed for standard MCP servers.
