/** Server-only settings loader and local Next.js launcher. */
import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { resolve } from "node:path";
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { parse } from "yaml";

/** @returns {{apiOrigin: string, host: string, port: number, telemetry: boolean}} */
export function loadSettings() {
  const config = parse(readFileSync(new URL("../../config/config.yaml", import.meta.url), "utf8"));
  const frontend = config?.frontend, api = config?.api;
  for (const service of [frontend, api]) {
    if (!service || typeof service.host !== "string" || !/^[a-zA-Z0-9.:-]+$/.test(service.host) ||
        !Number.isInteger(service.port) || service.port < 1 || service.port > 65535) {
      throw new Error("Host atau port layanan pada config/config.yaml tidak valid.");
    }
  }
  if (typeof frontend.telemetry !== "boolean") throw new Error("Pengaturan telemetry frontend harus boolean.");
  return { apiOrigin: new URL("http://" + api.host + ":" + api.port).origin,
    host: frontend.host, port: frontend.port, telemetry: frontend.telemetry };
}
if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  const command = process.argv[2];
  if (!["dev", "build", "start"].includes(command)) throw new Error("Perintah frontend tidak dikenal.");
  const settings = loadSettings();
  const require = createRequire(import.meta.url);
  const args = [require.resolve("next/dist/bin/next"), command];
  if (command !== "build") args.push("--hostname", settings.host, "--port", String(settings.port));
  const child = spawn(process.execPath, args, {
    cwd: fileURLToPath(new URL("../", import.meta.url)),
    env: { ...process.env, NEXT_TELEMETRY_DISABLED: settings.telemetry ? "0" : "1" },
    stdio: "inherit", windowsHide: true,
  });
  for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
  child.on("error", () => { process.stderr.write("Frontend belum dapat dijalankan.\n"); process.exitCode = 1; });
  child.on("exit", (code) => { process.exitCode = code ?? 1; });
}
