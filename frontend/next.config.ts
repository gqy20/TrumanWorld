import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: path.join(__dirname, ".."),
  allowedDevOrigins: ["127.0.0.1", "localhost", "*.local", "10.*", "172.*", "192.168.*"],
};

export default nextConfig;
