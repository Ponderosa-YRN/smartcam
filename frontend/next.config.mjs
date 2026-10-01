/** @type {import('next').NextConfig} */
// The browser talks to its own origin under /smartapi and Next.js proxies it to the
// SmartCam control plane. Same-origin means no CORS, and it keeps working on hotel
// networks that block or mangle direct requests to the API domain.
const API_ORIGIN = process.env.SMART_CAM_API_ORIGIN || "https://agay.tech";

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/smartapi/:path*",
        destination: API_ORIGIN + "/:path*",
      },
    ];
  },
};

export default nextConfig;
