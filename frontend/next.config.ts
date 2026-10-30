import type { NextConfig } from "next";

/**
 * The browser never calls the FastAPI backend directly. `/api/*` and `/health` are
 * rewritten to it, so the httpOnly `leaklens_session` cookie stays first-party in every
 * deployment and no CORS is involved. NEXT_PUBLIC_API_URL is read at build time.
 */
const apiUrl = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${apiUrl}/api/:path*` },
      { source: "/health", destination: `${apiUrl}/health` },
      { source: "/health/:path*", destination: `${apiUrl}/health/:path*` },
    ];
  },
};

export default nextConfig;
