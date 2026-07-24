import { cva, type VariantProps } from "class-variance-authority"
import type { ComponentProps } from "react"

import { cn } from "@/lib/utils"

const buttonVariants = cva("btn", {
  variants: {
    mode: {
      primary: "btn-primary",
      secondary: "btn-secondary",
    },
  },
  defaultVariants: {
    mode: "primary",
  },
})

type ButtonProps = ComponentProps<"button"> & VariantProps<typeof buttonVariants>

export function Button({ className, mode, type = "button", ...props }: ButtonProps) {
  return <button className={cn(buttonVariants({ mode }), className)} type={type} {...props} />
}
