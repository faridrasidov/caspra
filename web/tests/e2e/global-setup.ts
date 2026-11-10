import { createServer, type ViteDevServer } from "vite";
import { spawn, type ChildProcess } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

const live = process.env.CASPRA_E2E_REAL === "1";
const port = live ? 5175 : 5173;
const baseUrl = `http://127.0.0.1:${port}`;

async function isReady(url: string) { try { return (await fetch(url)).ok; } catch { return false; } }

export default async function globalSetup() {
  let backend: ChildProcess | undefined;
  let server: ViteDevServer | undefined;
  try {
    if (!live && await isReady(baseUrl)) return;
    if (live) {
      if (await isReady("http://127.0.0.1:18005/api/v1/health/live")) throw new Error("Test API port 18005 is already in use");
      const root = resolve("..");
      const candidate = resolve(root, process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python");
      backend = spawn(existsSync(candidate) ? candidate : "python", ["-m", "tests.serve_dashboard", "--port", "18005"], { cwd: root, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
      let output = "";
      backend.stderr?.on("data", data => { output = (output + String(data)).slice(-3000); });
      let ready = false;
      for (let attempt = 0; attempt < 200; attempt++) {
        if (backend.exitCode !== null) throw new Error(`Test API exited: ${output}`);
        if (await isReady("http://127.0.0.1:18005/api/v1/health/live")) { ready = true; break; }
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      if (!ready) throw new Error(`Test API did not become ready: ${output}`);
    }
    server = await createServer({ server: { host: "127.0.0.1", port, strictPort: true, ...(live ? { proxy: { "/admin/api": "http://127.0.0.1:18005", "/customer/api": "http://127.0.0.1:18005", "/api": "http://127.0.0.1:18005" } } : {}) } });
    await server.listen();
  } catch (error) { await server?.close(); backend?.kill(); throw error; }
  return async () => { await server?.close(); backend?.kill(); };
}
