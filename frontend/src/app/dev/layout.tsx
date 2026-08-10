import { notFound } from "next/navigation"
import type { ReactNode } from "react"

/**
 * 开发专用的组件预览区(PR2 验收工具):与 frontend/showcase/*.html 的规格页
 * 逐节对应,供并排截图比对。生产环境一律 404。
 */
export default function DevLayout({ children }: { readonly children: ReactNode }) {
  if (process.env.NODE_ENV !== "development") {
    notFound()
  }
  return children
}
