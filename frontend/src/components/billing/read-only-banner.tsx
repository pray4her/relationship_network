import { Alert, AlertDescription } from "@/components/ui/alert"

export function ReadOnlyBanner() {
  return (
    <Alert variant="destructive">
      <AlertDescription>
        订阅已到期，当前处于只读模式：你的数据已完整保留，可正常查看与导出；重新订阅后即可恢复全部功能。
      </AlertDescription>
    </Alert>
  )
}
