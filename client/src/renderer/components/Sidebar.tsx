import React, { useState } from "react";

type NavId = "agent" | "mcp" | "settings";

interface Props {
  connected: boolean;
  status: "idle" | "busy" | "error";
  onInterrupt: () => void;
}

const STATUS_COLORS = {
  idle: "rgba(100, 220, 100, 0.8)",
  busy: "rgba(255, 180, 0, 0.9)",
  error: "rgba(255, 60, 60, 0.9)",
};

export function Sidebar({ connected, status, onInterrupt }: Props) {
  const [open, setOpen] = useState(false);
  const [activeNav, setActiveNav] = useState<NavId | null>(null);

  return (
    <div className={`sidebar ${open ? "sidebar--open" : ""}`}>
      <button
        className="sidebar__toggle"
        onClick={() => setOpen((v) => !v)}
        title="Toggle sidebar"
      >
        <HamburgerIcon />
      </button>

      <div className="sidebar__content">
        <div className="sidebar__header">
          <div className="sidebar__status">
            <span
              className="sidebar__status-dot"
              style={{ background: STATUS_COLORS[status] }}
            />
            <span className="sidebar__status-label">
              {connected ? status : "disconnected"}
            </span>
          </div>

          {status === "busy" && (
            <button className="sidebar__interrupt-btn" onClick={onInterrupt}>
              Stop
            </button>
          )}
        </div>

        <nav className="sidebar__nav">
          <NavItem
            id="agent"
            label="Agent Mode"
            icon={<AgentIcon />}
            active={activeNav === "agent"}
            onClick={() => setActiveNav((v) => (v === "agent" ? null : "agent"))}
          />
          <NavItem
            id="mcp"
            label="MCP Servers"
            icon={<McpIcon />}
            active={activeNav === "mcp"}
            onClick={() => setActiveNav((v) => (v === "mcp" ? null : "mcp"))}
          />
          <NavItem
            id="settings"
            label="Settings"
            icon={<SettingsIcon />}
            active={activeNav === "settings"}
            onClick={() => setActiveNav((v) => (v === "settings" ? null : "settings"))}
          />
        </nav>
      </div>
    </div>
  );
}

function NavItem({
  label,
  icon,
  active,
  onClick,
}: {
  id: NavId;
  label: string;
  icon: React.ReactNode;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button className={`nav-item ${active ? "nav-item--active" : ""}`} onClick={onClick}>
      <span className="nav-icon">{icon}</span>
      <span className="nav-label">{label}</span>
    </button>
  );
}

function HamburgerIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      <rect x="1" y="3" width="16" height="1.5" rx="0.75" fill="currentColor" />
      <rect x="1" y="8.25" width="16" height="1.5" rx="0.75" fill="currentColor" />
      <rect x="1" y="13.5" width="16" height="1.5" rx="0.75" fill="currentColor" />
    </svg>
  );
}

function AgentIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
      <circle cx="10" cy="8" r="3.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M3 17c0-3.314 3.134-6 7-6s7 2.686 7 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function McpIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
      <rect x="3" y="6" width="14" height="9" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M7 6V5a3 3 0 0 1 6 0v1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="10" cy="10.5" r="1.5" fill="currentColor" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
      <circle cx="10" cy="10" r="2.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M10 2v1.5M10 16.5V18M2 10h1.5M16.5 10H18M4.1 4.1l1.06 1.06M14.84 14.84l1.06 1.06M4.1 15.9l1.06-1.06M14.84 5.16l1.06-1.06" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}
