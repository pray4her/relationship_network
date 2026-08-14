/**
 * 全站统一的展示格式化（替代各页本地拷贝）。
 * 时间统一 zh-CN 24 小时制；字节统一人类可读单位。
 */
export function formatDateTime(value: string | number | Date): string {
  return new Date(value).toLocaleString("zh-CN", { hour12: false })
}

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "—"
  if (bytes < 1024) return `${bytes} B`
  const units = ["KB", "MB", "GB"] as const
  let size = bytes / 1024
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex += 1
  }
  const rounded = size >= 100 ? Math.round(size).toString() : size.toFixed(1)
  return `${rounded} ${units[unitIndex]}`
}
