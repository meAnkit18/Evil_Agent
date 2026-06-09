import React from "react";
import type { ActiveTool } from "../types";

interface Props {
  tool: ActiveTool | null;
  status: "idle" | "busy" | "error";
}

const TOOL_LABELS: Record<string, string> = {
  bash: "running shell command",
  read: "reading file",
  write: "writing file",
  edit: "editing file",
  glob: "searching files",
  grep: "searching content",
  screenshot: "capturing screen",
  mouse_move: "moving mouse",
  mouse_click: "clicking",
  type_text: "typing",
  key_press: "pressing keys",
  open_app: "opening app",
};

export function ToolActivity({ tool, status }: Props) {
  if (!tool && status !== "busy") return null;

  const label = tool ? (TOOL_LABELS[tool.name] ?? tool.name) : "thinking...";

  return (
    <div className="tool-activity">
      <span className="tool-activity__spinner" />
      <span className="tool-activity__label">{label}</span>
      {tool && (
        <span className="tool-activity__name">{tool.name}</span>
      )}
    </div>
  );
}
