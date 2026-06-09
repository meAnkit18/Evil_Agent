import { z } from "zod";
import { spawn } from "child_process";
import type { ToolDef } from "./tool.ts";

const MAX_OUTPUT = 50_000;
const DEFAULT_TIMEOUT = 120_000; // 2 minutes

const params = z.object({
  command: z.string().describe("Shell command to execute"),
  cwd: z.string().optional().describe("Working directory (defaults to session workingDir)"),
  timeout: z.number().optional().describe("Timeout in milliseconds (default: 120000)"),
});

export const shellTool: ToolDef<z.infer<typeof params>> = {
  name: "bash",
  description:
    "Execute a shell command. Output is captured and returned. Long-running commands time out.",
  parameters: params,
  permission: "ask_once",

  async execute({ command, cwd, timeout }, ctx) {
    const workDir = cwd ?? ctx.workingDir;
    const ms = timeout ?? DEFAULT_TIMEOUT;

    return new Promise<{ output: string }>((resolve) => {
      const chunks: Buffer[] = [];
      let tooLong = false;

      const proc = spawn("bash", ["-c", command], {
        cwd: workDir,
        env: process.env,
        stdio: ["ignore", "pipe", "pipe"],
      });

      if (ctx.signal) {
        ctx.signal.addEventListener("abort", () => proc.kill("SIGTERM"));
      }

      const collect = (data: Buffer) => {
        if (!tooLong) {
          chunks.push(data);
          const total = chunks.reduce((n, c) => n + c.length, 0);
          if (total > MAX_OUTPUT) tooLong = true;
        }
      };

      proc.stdout.on("data", collect);
      proc.stderr.on("data", collect);

      const timer = setTimeout(() => {
        proc.kill("SIGTERM");
        resolve({ output: `Command timed out after ${ms}ms` });
      }, ms);

      proc.on("close", (code) => {
        clearTimeout(timer);
        let out = Buffer.concat(chunks).toString("utf8");
        if (tooLong) out = out.slice(0, MAX_OUTPUT) + "\n... (output truncated)";
        const suffix = code !== 0 ? `\nExit code: ${code}` : "";
        resolve({ output: out + suffix });
      });

      proc.on("error", (err) => {
        clearTimeout(timer);
        resolve({ output: `Error: ${err.message}` });
      });
    });
  },
};
