import { cva, type VariantProps } from "class-variance-authority"
import type { ComponentProps } from "react"

import { cn } from "@/lib/utils"

const cardVariants = cva("card", {
  variants: {
    tone: {
      panel: "card-panel",
      plain: "",
    },
  },
  defaultVariants: {
    tone: "panel",
  },
})

type CardProps = ComponentProps<"div"> & VariantProps<typeof cardVariants>

export function Card({ className, tone, ...props }: CardProps) {
  return <div className={cn(cardVariants({ tone }), className)} {...props} />
}
