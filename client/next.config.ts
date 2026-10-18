import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  // Keep the dev badge out of the app and its screenshots; errors still show.
  devIndicators: false,
  experimental: {
    // The /api proxy gives up after 30 s by default, which a slow free LLM can exceed and the
    // browser then sees as a 500. The server caps a turn at 45 s; the browser waits 60 s.
    proxyTimeout: 75_000,
  },
  // The FastAPI server owns all /api routes; proxying keeps the browser same-origin (no CORS).
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${process.env.API_URL ?? "http://127.0.0.1:8000"}/api/:path*` }];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
