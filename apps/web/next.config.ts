import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: ".next",
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
