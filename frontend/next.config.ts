import type { NextConfig } from "next";
import { loadSettings } from "./scripts/run.mjs";

const settings = loadSettings();
process.env.NEXT_TELEMETRY_DISABLED = settings.telemetry ? "0" : "1";
const config: NextConfig = {
  async rewrites() { return [{ source: "/api/:path*", destination: settings.apiOrigin + "/api/:path*" }]; },
};
export default config;
