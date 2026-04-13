import type { NextConfig } from "next";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8002";

const nextConfig: NextConfig = {
  experimental: {
    proxyTimeout: 300_000, // 5 min — wiki/structure can be slow on large repos
  },
  async rewrites() {
    return [
      { source: "/wiki/:path*",   destination: `${API_URL}/wiki/:path*` },
      { source: "/chat/:path*",   destination: `${API_URL}/chat/:path*` },
      { source: "/api/:path*",    destination: `${API_URL}/api/:path*` },
      { source: "/models/config", destination: `${API_URL}/models/config` },
      { source: "/lang/config",   destination: `${API_URL}/lang/config` },
      { source: "/health",        destination: `${API_URL}/health` },
    ];
  },
};

export default nextConfig;
