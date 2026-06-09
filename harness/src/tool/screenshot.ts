import { z } from "zod";
import type { ToolDef } from "./tool.ts";

const params = z.object({
  screen: z.number().int().min(0).optional().describe("Monitor index (0 = primary)"),
});

export const screenshotTool: ToolDef<z.infer<typeof params>> = {
  name: "screenshot",
  description:
    "Capture the current screen as an image. Returns a base64-encoded PNG that you can visually analyze to understand what is on the screen.",
  parameters: params,
  permission: "auto",

  async execute({ screen = 0 }) {
    const { default: screenshot } = await import("screenshot-desktop");
    const imgBuffer: Buffer = await screenshot({ screen });
    const base64 = imgBuffer.toString("base64");

    return {
      output: JSON.stringify({
        type: "image",
        media_type: "image/png",
        data: base64,
      }),
      metadata: { imageBase64: base64, mediaType: "image/png" },
    };
  },
};
