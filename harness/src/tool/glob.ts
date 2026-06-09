import { z } from "zod";
import fg from "fast-glob";
import type { ToolDef } from "./tool.ts";

const params = z.object({
  pattern: z.string().describe("Glob pattern, e.g. 'src/**/*.ts'"),
  cwd: z.string().optional().describe("Directory to search from (defaults to session workingDir)"),
});

export const globTool: ToolDef<z.infer<typeof params>> = {
  name: "glob",
  description: "Find files matching a glob pattern.",
  parameters: params,
  permission: "auto",

  async execute({ pattern, cwd }, ctx) {
    const searchDir = cwd ?? ctx.workingDir;
    const files = await fg(pattern, { cwd: searchDir, dot: true, absolute: false });

    if (files.length === 0) {
      return { output: "No files matched." };
    }

    return { output: files.slice(0, 500).join("\n") };
  },
};
