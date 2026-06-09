import { z } from "zod";
import type { ToolDef } from "./tool.ts";

const params = z.object({
  target: z
    .string()
    .describe("Application name, executable path, file path, or URL to open"),
});

export const appLaunchTool: ToolDef<z.infer<typeof params>> = {
  name: "open_app",
  description:
    "Open an application, file, or URL using the system default handler. Examples: 'firefox', '/usr/bin/code', '~/Documents/file.pdf', 'https://example.com'.",
  parameters: params,
  permission: "ask_once",

  async execute({ target }) {
    const { default: open } = await import("open");
    await open(target);
    return { output: `Opened: ${target}` };
  },
};
