import type { NextConfig } from "next"

const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  // PR2 截图验收需要无干扰的页面渲染
  devIndicators: false,
} satisfies NextConfig

export default nextConfig
