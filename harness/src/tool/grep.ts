import { z } from "zod";
import { execFile } from "child_process";
import { promisify } from "util";
import type { ToolDef } from "./tool.ts";

const execFileAsync = promisify(execFile);

const params = z.object({
  pattern: z.string().describe("Search pattern (regex)"),
  path: z.string().optional().describe("File or directory to search (defaults to workingDir)"),
  case_insensitive: z.boolean().optional().describe("Case-insensitive search"),
});

export const grepTool: ToolDef<z.infer<typeof params>> = {
  name: "grep",
  description: "Search file contents for a pattern using ripgrep (rg). Falls back to grep.",
  parameters: params,
  permission: "auto",

  async execute({ pattern, path, case_insensitive }, ctx) {
    const searchPath = path
      ? path.startsWith("/") ? path : `${ctx.workingDir}/${path}`
      : ctx.workingDir;

    const args = ["-n", "--no-heading", "--color=never"];
    if (case_insensitive) args.push("-i");
    args.push(pattern, searchPath);

    const command = await hasRipgrep() ? "rg" : "grep";
    if (command === "grep") {
      args.unshift("-r");
    }

    try {
      const { stdout } = await execFileAsync(command, args, { maxBuffer: 1024 * 1024 });
      const lines = stdout.trim().split("\n").slice(0, 200);
      return { output: lines.join("\n") || "No matches." };
    } catch (err: unknown) {
      const e = err as { code?: number; stdout?: string };
      if (e.code === 1) return { output: "No matches." };
      return { output: `Error: ${String(err)}` };
    }
  },
};

let _hasRg: boolean | null = null;
async function hasRipgrep(): Promise<boolean> {
  if (_hasRg !== null) return _hasRg;
  try {
    await execFileAsync("rg", ["--version"]);
    _hasRg = true;
  } catch {
    _hasRg = false;
  }
  return _hasRg;
}
