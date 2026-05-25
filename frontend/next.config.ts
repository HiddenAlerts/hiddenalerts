import type { NextConfig } from "next";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Keep module resolution anchored to `frontend/` when a lockfile exists at the repo root.
const appRoot = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  turbopack: {
    root: appRoot,
  },
};

export default nextConfig;
