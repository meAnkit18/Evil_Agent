import { z } from "zod";
import { readFileSync, writeFileSync, existsSync } from "fs";
import type { ToolDef } from "./tool.ts";

const params = z.object({
  path: z.string().describe("Path to the file to edit"),
  old_string: z.string().describe("Exact string to find and replace — must be unique in the file"),
  new_string: z.string().describe("Replacement string"),
});

export const editTool: ToolDef<z.infer<typeof params>> = {
  name: "edit",
  description:
    "Replace an exact string in a file. The old_string must appear exactly once. Use read first to verify the exact content.",
  parameters: params,
  permission: "ask_once",

  async execute({ path, old_string, new_string }, ctx) {
    const fullPath = path.startsWith("/") ? path : `${ctx.workingDir}/${path}`;

    if (!existsSync(fullPath)) {
      return { output: `Error: file not found: ${fullPath}` };
    }

    const content = readFileSync(fullPath, "utf8");
    const count = content.split(old_string).length - 1;

    if (count === 0) {
      return { output: `Error: old_string not found in ${fullPath}` };
    }
    if (count > 1) {
      return {
        output: `Error: old_string appears ${count} times — provide more context to make it unique`,
      };
    }

    writeFileSync(fullPath, content.replace(old_string, new_string), "utf8");
    return { output: `Edited ${fullPath}`, files: [fullPath] };
  },
};
