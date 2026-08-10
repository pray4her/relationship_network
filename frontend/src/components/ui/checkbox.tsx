"use client"

import { Checkbox as CheckboxPrimitive } from "@base-ui/react/checkbox"
import { cva, type VariantProps } from "class-variance-authority"
import { CheckIcon, MinusIcon } from "lucide-react"

import { cn } from "@/lib/utils"

/** 视觉规格：frontend/src/styles/checkbox.css。 */
const checkboxVariants = cva(
  "group/checkbox peer relative flex shrink-0 cursor-pointer items-center justify-center rounded-[var(--radius-xs)] border-[length:var(--border-width)] border-input bg-background text-transparent outline-none transition-[background-color,border-color,box-shadow] duration-fast ease-standard after:absolute after:-inset-x-[var(--space-3)] after:-inset-y-[var(--space-2)] hover:border-border-strong active:bg-surface-cream-strong focus-visible:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] data-[state=hover]:border-border-strong data-[state=active]:bg-surface-cream-strong data-[state=focus-visible]:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] data-checked:border-selected-border data-checked:bg-selected-border data-checked:text-primary-foreground data-indeterminate:border-selected-border data-indeterminate:bg-selected-border data-indeterminate:text-primary-foreground hover:data-checked:border-primary-hover hover:data-checked:bg-primary-hover hover:data-indeterminate:border-primary-hover hover:data-indeterminate:bg-primary-hover active:data-checked:border-primary-active active:data-checked:bg-primary-active active:data-indeterminate:border-primary-active active:data-indeterminate:bg-primary-active aria-invalid:border-destructive aria-invalid:focus-visible:shadow-[0_0_0_var(--ring-width)_var(--ring-destructive)] aria-invalid:data-[state=focus-visible]:shadow-[0_0_0_var(--ring-width)_var(--ring-destructive)] disabled:cursor-not-allowed disabled:opacity-[var(--opacity-disabled)] group-has-disabled/field:opacity-[var(--opacity-disabled)] motion-reduce:transition-none",
  {
    variants: {
      size: {
        sm: "size-[var(--checkbox-size-sm)]",
        default: "size-[var(--checkbox-size-md)]",
        lg: "size-[var(--checkbox-size-lg)]",
      },
    },
    defaultVariants: { size: "default" },
  },
)

type CheckboxProps = CheckboxPrimitive.Root.Props & VariantProps<typeof checkboxVariants>

function Checkbox({ className, size = "default", ...props }: CheckboxProps) {
  return (
    <CheckboxPrimitive.Root
      className={cn(checkboxVariants({ size }), className)}
      data-size={size}
      data-slot="checkbox"
      {...props}
    >
      <CheckboxPrimitive.Indicator
        className="grid size-full place-content-center text-current transition-none [&_svg]:size-[var(--icon-size-xs)] group-data-[size=lg]/checkbox:[&_svg]:size-[var(--icon-size-sm)]"
        data-slot="checkbox-indicator"
      >
        <CheckIcon className="group-data-indeterminate/checkbox:hidden" />
        <MinusIcon className="hidden group-data-indeterminate/checkbox:block" />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  )
}

export { Checkbox, checkboxVariants }
