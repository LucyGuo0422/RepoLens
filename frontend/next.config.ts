import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/wiki/:path*",   destination: "http://localhost:8002/wiki/:path*" },
      { source: "/chat/:path*",   destination: "http://localhost:8002/chat/:path*" },
      { source: "/api/:path*",    destination: "http://localhost:8002/api/:path*" },
      { source: "/models/config", destination: "http://localhost:8002/models/config" },
      { source: "/lang/config",   destination: "http://localhost:8002/lang/config" },
      { source: "/health",        destination: "http://localhost:8002/health" },
    ];
  },
};

export default nextConfig;
