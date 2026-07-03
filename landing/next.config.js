/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['three'],
  experimental: {
    optimizePackageImports: ['@react-three/drei'],
  },
  // Static HTML export — writes to ./out on `next build`. Renderable by any
  // static host: Render Static Site, Cloudflare Pages, GitHub Pages, S3+CF.
  // No server runtime required; 3D scenes still work because they're all
  // wrapped in next/dynamic({ ssr: false }).
  output: 'export',
  images: {
    // Static export can't use next/image's default optimizer (no server).
    // We're not using next/image right now anyway, but flip this on so
    // when we do it doesn't fail.
    unoptimized: true,
  },
  // Add trailing slashes so Render's static-site routing matches paths
  // like /about/ correctly. Harmless for the single-page landing today.
  trailingSlash: true,
};

module.exports = nextConfig;
