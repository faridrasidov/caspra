import { createServer, type ViteDevServer } from "vite";

const baseUrl = "http://127.0.0.1:5173";

async function hasExistingServer() {
  try {
    const response = await fetch(baseUrl);
    return response.ok;
  } catch {
    return false;
  }
}

export default async function globalSetup() {
  if (await hasExistingServer()) return;

  let server: ViteDevServer | undefined;

  try {
    server = await createServer({
      server: {
        host: "127.0.0.1",
        port: 5173,
        strictPort: true,
      },
    });
    await server.listen();
  } catch (error) {
    await server?.close();
    throw error;
  }

  return async () => {
    await server.close();
  };
}
