import type { ComponentProps } from "react"

import { cn } from "@/lib/utils"

type LabelProps = ComponentProps<"label">

export function Label({ className, ...props }: LabelProps) {
  // biome-ignore lint/a11y/noLabelWithoutControl: callers always pass htmlFor
  return <label className={cn("field-label", className)} {...props} />
}
