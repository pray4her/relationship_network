import { cva, type VariantProps } from "class-variance-authority"
import type { ComponentProps } from "react"

import { cn } from "@/lib/utils"

const inputVariants = cva("field-input", {
  variants: {
    invalid: {
      true: "field-input-invalid",
      false: "",
    },
  },
  defaultVariants: {
    invalid: false,
  },
})

type InputProps = ComponentProps<"input"> & VariantProps<typeof inputVariants>

export function Input({ className, invalid, ...props }: InputProps) {
  return <input className={cn(inputVariants({ invalid }), className)} {...props} />
}
