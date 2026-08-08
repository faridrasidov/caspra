import { readdir, readFile } from "node:fs/promises";
import { extname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../src/", import.meta.url));
const failures = [];
const bannedImports =
  /from\s+["'](?:lucide(?:-\w+)?|react-icons|@heroicons\/[^"']+|@fortawesome\/[^"']+|@mui\/icons-material)["']/;

async function inspect(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      await inspect(path);
      continue;
    }
    if (
      ![".ts", ".tsx", ".js", ".jsx", ".vue", ".html"].includes(extname(entry.name)) ||
      entry.name === "schema.d.ts"
    ) {
      continue;
    }
    const source = await readFile(path, "utf8");
    const label = relative(root, path);
    if (bannedImports.test(source)) failures.push(`${label}: non-Remix icon import`);
    if (/<svg(?:\s|>)/i.test(source)) failures.push(`${label}: hand-authored inline SVG`);
    if (/\b(?:React|lucide|recharts)\b/.test(source)) {
      failures.push(`${label}: React, Lucide, or Recharts remnant`);
    }
  }
}

await inspect(root);

if (failures.length) {
  console.error(failures.join("\n"));
  process.exitCode = 1;
} else {
  console.log("Remix Icon source audit passed");
}
