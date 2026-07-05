import type { NextConfig } from 'next';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const appRoot = path.dirname(fileURLToPath(import.meta.url));

const API_PROXY_TARGET = 'https://api.hiddenalerts.com';

const nextConfig: NextConfig = {
  turbopack: {
    root: appRoot,
  },
  async rewrites() {
    if (process.env.NODE_ENV !== 'development') return [];
    return [
      {
        source: '/_proxy/api/:path*',
        destination: `${API_PROXY_TARGET}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
