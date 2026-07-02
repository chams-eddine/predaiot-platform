/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['three'],
  experimental: {
    optimizePackageImports: ['lucide-react', '@react-three/drei'],
  },
};

module.exports = nextConfig;
