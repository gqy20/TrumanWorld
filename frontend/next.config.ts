import type { NextConfig } from "next";
import path from "path";

const railwayInternalApiBaseUrl = process.env.RAILWAY_SERVICE_BACKEND_URL
  ? `https://${process.env.RAILWAY_SERVICE_BACKEND_URL.replace(/\/$/, "")}/api`
  : undefined;
const internalApiBaseUrl =
  process.env.INTERNAL_API_BASE_URL?.replace(/\/$/, "") ??
  railwayInternalApiBaseUrl ??
  "http://127.0.0.1:18080/api";
const extraAllowedDevOrigins =
  process.env.NEXT_ALLOWED_DEV_ORIGINS?.split(",")
    .map((origin) => origin.trim())
    .filter(Boolean) ?? [];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: path.join(__dirname, ".."),
  allowedDevOrigins: [
    "127.0.0.1",
    "localhost",
    "*.local",
    "10.*",
    "172.*",
    "192.168.*",
    "10.10.11.153",
    "100.79.129.46",
    ...extraAllowedDevOrigins,
  ],
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${internalApiBaseUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
