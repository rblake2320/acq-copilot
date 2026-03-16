import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: ".next",
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: true },
  rewrites: async () => {
    return {
      beforeFiles: [
        {
          source: "/api/:path*",
          destination: "http://localhost:8002/api/:path*",
        },
      ],
    };
  },
};

export default nextConfig;
