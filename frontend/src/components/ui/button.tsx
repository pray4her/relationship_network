import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/**
 * 视觉规格:frontend/src/styles/button.css + icon-button.css(showcase 为唯一标准)。
 * 状态同时挂伪类与 data-[state=*] 镜像,预览页可静态渲染 hover/active/focus 态。
 */
const buttonVariants = cva(
  "group/button relative inline-flex shrink-0 cursor-pointer items-center justify-center gap-[var(--space-2)] rounded-[var(--radius-md)] border border-transparent bg-clip-padding font-sans text-[length:var(--text-button)] leading-none font-medium whitespace-nowrap outline-none select-none transition-[background-color,color,border-color,box-shadow,opacity] duration-fast ease-standard focus-visible:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-[var(--opacity-disabled)] data-[state=focus-visible]:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-[var(--icon-size-sm)] [&_svg_path]:[stroke-width:var(--stroke-width-icon)]",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground hover:bg-primary-hover active:bg-primary-active data-[state=hover]:bg-primary-hover data-[state=active]:bg-primary-active [&_[data-slot=button-spinner]]:border-primary-foreground",
        secondary:
          "border-border bg-secondary text-secondary-foreground hover:bg-accent active:bg-surface-cream-strong data-[state=hover]:bg-accent data-[state=active]:bg-surface-cream-strong [&_[data-slot=button-spinner]]:border-secondary-foreground",
        outline:
          "border-border bg-secondary text-secondary-foreground hover:bg-accent active:bg-surface-cream-strong data-[state=hover]:bg-accent data-[state=active]:bg-surface-cream-strong [&_[data-slot=button-spinner]]:border-secondary-foreground",
        ghost:
          "text-foreground hover:bg-accent active:bg-surface-cream-strong data-[state=hover]:bg-accent data-[state=active]:bg-surface-cream-strong [&_[data-slot=button-spinner]]:border-foreground",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive-hover active:bg-destructive-active data-[state=hover]:bg-destructive-hover data-[state=active]:bg-destructive-active [&_[data-slot=button-spinner]]:border-destructive-foreground",
        link: "h-auto cursor-pointer gap-[var(--space-1)] rounded-[var(--radius-xs)] border-0 px-0 text-primary underline decoration-[var(--border-width)] underline-offset-[var(--link-underline-offset)] transition-colors hover:text-primary-hover hover:underline active:text-primary-active data-[state=hover]:text-primary-hover data-[state=hover]:underline data-[state=active]:text-primary-active",
      },
      size: {
        default: "h-[var(--control-height)] px-[var(--button-padding-inline)]",
        xs: "h-[var(--control-height-sm)] px-[var(--button-padding-inline-sm)]",
        sm: "h-[var(--control-height-sm)] px-[var(--button-padding-inline-sm)]",
        lg: "h-[var(--control-height-lg)] px-[var(--button-padding-inline-lg)]",
        icon: "size-[var(--icon-button-size)] rounded-[var(--radius-full)] px-0",
        "icon-xs":
          "size-[var(--control-height-sm)] rounded-[var(--radius-full)] px-0 [&_svg:not([class*='size-'])]:size-[var(--icon-size-xs)]",
        "icon-sm":
          "size-[var(--control-height-sm)] rounded-[var(--radius-full)] px-0 [&_svg:not([class*='size-'])]:size-[var(--icon-size-xs)]",
        "icon-lg":
          "size-[var(--control-height-lg)] rounded-[var(--radius-full)] px-0 [&_svg:not([class*='size-'])]:size-[var(--icon-size-lg)]",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
)

type ButtonProps = ButtonPrimitive.Props &
  VariantProps<typeof buttonVariants> & {
    /** 加载态:规格要求同时携带 disabled + aria-busy,内容保持布局但隐藏,spinner 居中覆盖。 */
    loading?: boolean
  }

function Button({
  className,
  variant = "default",
  size = "default",
  loading,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <ButtonPrimitive
      aria-busy={loading || undefined}
      className={cn(
        buttonVariants({ variant, size }),
        loading &&
          "pointer-events-none cursor-progress text-transparent disabled:opacity-100 [&_svg]:invisible",
        className,
      )}
      data-slot="button"
      disabled={loading || disabled}
      {...props}
    >
      {children}
      {loading && (
        <span
          aria-hidden="true"
          className="absolute top-1/2 left-1/2 size-[var(--icon-size-sm)] -translate-x-1/2 -translate-y-1/2 animate-spin rounded-full border-[length:var(--space-0-5)] border-solid border-t-transparent [animation-duration:var(--duration-loading)] [animation-timing-function:linear]"
          data-slot="button-spinner"
        />
      )}
    </ButtonPrimitive>
  )
}

export { Button, buttonVariants }
