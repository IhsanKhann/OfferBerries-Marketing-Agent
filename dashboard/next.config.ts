import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  output: 'standalone',
  images: {
    remotePatterns: [
      { protocol: 'http', hostname: 'renderer' },
      { protocol: 'http', hostname: 'localhost' },
    ],
  },
  serverExternalPackages: [],
};

export default nextConfig;
