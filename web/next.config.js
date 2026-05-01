const fs = require("node:fs");
const path = require("node:path");

const repoEnvPath = path.resolve(__dirname, "..", ".env");

if (fs.existsSync(repoEnvPath)) {
  const lines = fs.readFileSync(repoEnvPath, "utf8").split(/\r?\n/);
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }

    const separatorIndex = trimmed.indexOf("=");
    if (separatorIndex === -1) {
      continue;
    }

    const key = trimmed.slice(0, separatorIndex).trim();
    const value = trimmed.slice(separatorIndex + 1).trim().replace(/^['"]|['"]$/g, "");
    if (key.startsWith("NEXT_PUBLIC_") && process.env[key] === undefined) {
      process.env[key] = value;
    }
  }
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
};

module.exports = nextConfig;
