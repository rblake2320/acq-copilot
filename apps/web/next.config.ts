import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: ".next",
  rewrites: async () => {
    return {
      beforeFiles: [
        {
          source: "/api/:path*",
          destination: "http://localhost:8001/api/:path*",
        },
      ],
    };
  },
};

export default nextConfig;
