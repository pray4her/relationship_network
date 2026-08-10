"use client"

import { Radio as RadioPrimitive } from "@base-ui/react/radio"
import { RadioGroup as RadioGroupPrimitive } from "@base-ui/react/radio-group"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

type RadioGroupProps = RadioGroupPrimitive.Props & {
  /** Base UI 没有 orientation prop；本属性只控制规格中的水平/垂直布局。 */
  orientation?: "horizontal" | "vertical"
}

function RadioGroup({ className, orientation = "vertical", ...props }: RadioGroupProps) {
  return (
    <RadioGroupPrimitive
      className={cn(
        "grid w-full gap-[var(--space-3)] data-[orientation=horizontal]:flex data-[orientation=horizontal]:flex-wrap data-[orientation=horizontal]:gap-x-[var(--space-6)] data-[orientation=horizontal]:gap-y-[var(--space-3)]",
        className,
      )}
      data-orientation={orientation}
      data-slot="radio-group"
      {...props}
    />
  )
}

/** 视觉规格：frontend/src/styles/radio.css。 */
const radioGroupItemVariants = cva(
  "group/radio peer relative flex shrink-0 cursor-pointer items-center justify-center rounded-[var(--radius-full)] border-[length:var(--border-width)] border-input bg-background outline-none transition-[background-color,border-color,box-shadow] duration-fast ease-standard after:absolute after:-inset-x-[var(--space-3)] after:-inset-y-[var(--space-2)] hover:border-border-strong active:border-primary-active active:bg-selected-bg focus-visible:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] data-[state=hover]:border-border-strong data-[state=active]:border-primary-active data-[state=active]:bg-selected-bg data-[state=focus-visible]:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] data-checked:border-selected-border hover:data-checked:border-primary-hover active:data-checked:border-primary-active aria-invalid:border-destructive aria-invalid:focus-visible:shadow-[0_0_0_var(--ring-width)_var(--ring-destructive)] aria-invalid:data-[state=focus-visible]:shadow-[0_0_0_var(--ring-width)_var(--ring-destructive)] disabled:cursor-not-allowed disabled:opacity-[var(--opacity-disabled)] group-has-disabled/field:opacity-[var(--opacity-disabled)] motion-reduce:transition-none",
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

type RadioGroupItemProps = RadioPrimitive.Root.Props & VariantProps<typeof radioGroupItemVariants>

function RadioGroupItem({ className, size = "default", ...props }: RadioGroupItemProps) {
  return (
    <RadioPrimitive.Root
      className={cn(radioGroupItemVariants({ size }), className)}
      data-size={size}
      data-slot="radio-group-item"
      {...props}
    >
      <RadioPrimitive.Indicator
        className="flex size-full items-center justify-center"
        data-slot="radio-group-indicator"
      >
        <span className="size-[calc(100%-var(--space-2))] rounded-[var(--radius-full)] bg-selected-border transition-colors duration-fast ease-standard group-hover/radio:bg-primary-hover group-active/radio:bg-primary-active group-data-[state=hover]/radio:bg-primary-hover group-data-[state=active]/radio:bg-primary-active motion-reduce:transition-none" />
      </RadioPrimitive.Indicator>
    </RadioPrimitive.Root>
  )
}

export { RadioGroup, RadioGroupItem, radioGroupItemVariants }
