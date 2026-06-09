import type { ZodSchema } from "zod";
import type { bus } from "../events/bus.ts";

export type PermissionLevel = "auto" | "ask_once" | "ask_always";

export interface ToolContext {
  sessionID: string;
  workingDir: string;
  signal: AbortSignal;
  emit: typeof bus.emit;
}

export interface ToolResult {
  output: string;
  metadata?: Record<string, unknown>;
  files?: string[];
}

export interface ToolDef<T = unknown> {
  name: string;
  description: string;
  parameters: ZodSchema<T>;
  execute(args: T, ctx: ToolContext): Promise<ToolResult>;
  permission?: PermissionLevel;
  agents?: string[]; // if set, only available to these agents
}
