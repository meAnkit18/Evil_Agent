import { createRoutes } from "./routes.ts";

export interface ServerOptions {
  port?: number;
  hostname?: string;
}

export interface ServerHandle {
  port: number;
  hostname: string;
  stop(): void;
}

export function startServer(opts: ServerOptions = {}): ServerHandle {
  const port = opts.port ?? parseInt(process.env.HARNESS_PORT ?? "7777");
  const hostname = opts.hostname ?? "127.0.0.1";

  const app = createRoutes();

  // CORS for renderer EventSource
  app.use("*", async (c, next) => {
    await next();
    c.header("Access-Control-Allow-Origin", "*");
    c.header("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    c.header("Access-Control-Allow-Headers", "Content-Type");
  });

  const server = Bun.serve({
    fetch: app.fetch,
    port,
    hostname,
  });

  console.log(`[harness] Server running on http://${hostname}:${port}`);

  return {
    port,
    hostname,
    stop() { server.stop(); },
  };
}
