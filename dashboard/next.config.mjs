/** @type {import('next').NextConfig} */
const nextConfig = {
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
