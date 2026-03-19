import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/wiki/:path*",   destination: "http://localhost:8001/wiki/:path*" },
      { source: "/chat/:path*",   destination: "http://localhost:8001/chat/:path*" },
      { source: "/api/:path*",    destination: "http://localhost:8001/api/:path*" },
      { source: "/models/config", destination: "http://localhost:8001/models/config" },
      { source: "/lang/config",   destination: "http://localhost:8001/lang/config" },
      { source: "/health",        destination: "http://localhost:8001/health" },
    ];
  },
};

export default nextConfig;
