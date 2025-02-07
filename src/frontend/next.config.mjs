/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: false,
  output: 'standalone',
  experimental: {
    // Enable if needed
    // esmExternals: true,
  }
};

export default nextConfig;