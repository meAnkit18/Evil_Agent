import type { ZodSchema } from "zod";
import type { ToolDef, ToolContext, ToolResult, PermissionLevel } from "./tool.ts";
import type { ToolSchema } from "../provider/provider.ts";
import { readTool } from "./read.ts";
import { writeTool } from "./write.ts";
import { editTool } from "./edit.ts";
import { globTool } from "./glob.ts";
import { grepTool } from "./grep.ts";
import { shellTool } from "./shell.ts";
import { screenshotTool } from "./screenshot.ts";
import { mouseMoveTool, mouseClickTool } from "./mouse.ts";
import { typeTextTool, keyPressTool } from "./keyboard.ts";
import { appLaunchTool } from "./app_launch.ts";

const ALL_TOOLS: ToolDef<unknown>[] = [
  readTool,
  writeTool,
  editTool,
  globTool,
  grepTool,
  shellTool,
  screenshotTool,
  mouseMoveTool,
  mouseClickTool,
  typeTextTool,
  keyPressTool,
  appLaunchTool,
];

const READ_ONLY_TOOLS = new Set(["read", "glob", "grep", "screenshot", "mouse_move"]);

export const toolRegistry = {
  getAll(): ToolDef<unknown>[] {
    return ALL_TOOLS;
  },

  getForAgent(agent: string): ToolDef<unknown>[] {
    if (agent === "plan" || agent === "explore") {
      return ALL_TOOLS.filter((t) => READ_ONLY_TOOLS.has(t.name));
    }
    return ALL_TOOLS;
  },

  toSchemas(tools: ToolDef<unknown>[]): ToolSchema[] {
    return tools.map((t) => ({
      name: t.name,
      description: t.description,
      input_schema: zodToJsonSchema(t.parameters),
    }));
  },

  async execute(
    name: string,
    args: unknown,
    ctx: ToolContext
  ): Promise<ToolResult> {
    const tool = ALL_TOOLS.find((t) => t.name === name);
    if (!tool) {
      return { output: `Error: unknown tool "${name}"` };
    }

    let parsed: unknown;
    try {
      parsed = tool.parameters.parse(args);
    } catch (err) {
      return { output: `Error: invalid arguments for ${name}: ${String(err)}` };
    }

    try {
      return await (tool as ToolDef<typeof parsed>).execute(parsed, ctx);
    } catch (err) {
      return { output: `Error executing ${name}: ${String(err)}` };
    }
  },

  getPermission(name: string): PermissionLevel {
    const tool = ALL_TOOLS.find((t) => t.name === name);
    return tool?.permission ?? "ask_once";
  },
};

function zodToJsonSchema(schema: ZodSchema): ToolSchema["input_schema"] {
  // Convert Zod schema description to JSON Schema subset
  // This is a simplified conversion sufficient for Anthropic's tool use
  const shape = (schema as { _def?: { shape?: () => Record<string, unknown> } })._def?.shape?.();
  if (!shape) {
    return { type: "object", properties: {} };
  }

  const properties: Record<string, unknown> = {};
  const required: string[] = [];

  for (const [key, fieldSchema] of Object.entries(shape)) {
    const field = fieldSchema as {
      _def?: {
        typeName?: string;
        description?: string;
        innerType?: { _def?: { typeName?: string; values?: string[] } };
        defaultValue?: () => unknown;
        checks?: Array<{ kind: string; value?: unknown }>;
        values?: string[];
      };
      isOptional?: () => boolean;
    };
    const def = field._def;
    const typeName = def?.typeName ?? "";
    const description = def?.description;
    const isOptional = def?.typeName === "ZodOptional" || def?.typeName === "ZodDefault" || field.isOptional?.();

    const innerType = def?.innerType?._def?.typeName ?? typeName;

    const prop: Record<string, unknown> = {};
    if (description) prop.description = description;

    if (innerType === "ZodString" || typeName === "ZodString") {
      prop.type = "string";
    } else if (innerType === "ZodNumber" || typeName === "ZodNumber") {
      prop.type = "number";
    } else if (innerType === "ZodBoolean" || typeName === "ZodBoolean") {
      prop.type = "boolean";
    } else if (typeName === "ZodEnum" || def?.innerType?._def?.typeName === "ZodEnum") {
      prop.type = "string";
      const values = def?.values ?? def?.innerType?._def?.values;
      if (values) prop.enum = values;
    } else {
      prop.type = "string";
    }

    properties[key] = prop;
    if (!isOptional) required.push(key);
  }

  return {
    type: "object",
    properties,
    ...(required.length > 0 ? { required } : {}),
  };
}
