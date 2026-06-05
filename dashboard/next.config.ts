import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@lobehub/icons"],
  experimental: {
    externalDir: true,
  },
};

export default nextConfig;
