import { z } from "zod";
import { writeFileSync, mkdirSync } from "fs";
import { dirname } from "path";
import type { ToolDef } from "./tool.ts";

const params = z.object({
  path: z.string().describe("Absolute or relative path to write"),
  content: z.string().describe("Full file content to write"),
});

export const writeTool: ToolDef<z.infer<typeof params>> = {
  name: "write",
  description: "Write content to a file, creating it and any parent directories if needed.",
  parameters: params,
  permission: "ask_once",

  async execute({ path, content }, ctx) {
    const fullPath = path.startsWith("/") ? path : `${ctx.workingDir}/${path}`;
    mkdirSync(dirname(fullPath), { recursive: true });
    writeFileSync(fullPath, content, "utf8");
    return { output: `Wrote ${content.length} chars to ${fullPath}`, files: [fullPath] };
  },
};
