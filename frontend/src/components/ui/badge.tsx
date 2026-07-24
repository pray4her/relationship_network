import { cva, type VariantProps } from "class-variance-authority"
import type { ComponentProps } from "react"

import { cn } from "@/lib/utils"

const badgeVariants = cva("inline-flex items-center", {
  variants: {
    mode: {
      local: "",
      recovery: "",
    },
  },
  defaultVariants: {
    mode: "local",
  },
})

type BadgeProps = ComponentProps<"span"> & VariantProps<typeof badgeVariants>

export function Badge({ className, mode, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ mode }), className)} {...props} />
}
