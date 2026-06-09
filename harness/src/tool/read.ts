import { z } from "zod";
import { readFileSync, existsSync } from "fs";
import type { ToolDef } from "./tool.ts";

const MAX_CHARS = 50_000;

const params = z.object({
  path: z.string().describe("Absolute or relative path to the file"),
  start_line: z.number().int().min(1).optional().describe("First line to read (1-indexed)"),
  end_line: z.number().int().min(1).optional().describe("Last line to read (inclusive)"),
});

export const readTool: ToolDef<z.infer<typeof params>> = {
  name: "read",
  description: "Read the contents of a file. Optionally specify a line range.",
  parameters: params,
  permission: "auto",

  async execute({ path, start_line, end_line }, ctx) {
    const fullPath = path.startsWith("/") ? path : `${ctx.workingDir}/${path}`;

    if (!existsSync(fullPath)) {
      return { output: `Error: file not found: ${fullPath}` };
    }

    const raw = readFileSync(fullPath, "utf8");
    const lines = raw.split("\n");

    const from = (start_line ?? 1) - 1;
    const to = end_line ?? lines.length;
    const slice = lines.slice(from, to);

    const numbered = slice
      .map((line, i) => `${(from + i + 1).toString().padStart(4)}\t${line}`)
      .join("\n");

    const truncated = numbered.length > MAX_CHARS
      ? numbered.slice(0, MAX_CHARS) + `\n... (truncated, ${lines.length} total lines)`
      : numbered;

    return { output: truncated };
  },
};
