import type * as React from "react"

import { cn } from "@/lib/utils"

/** admin 域筛选用的原生 select，统一尺寸与焦点样式（GET 表单语义不变）。 */
function FilterSelect({ className, ...props }: React.ComponentProps<"select">) {
  return (
    <select
      className={cn(
        "h-8 w-auto rounded-md border border-input bg-transparent px-2 text-sm transition-colors outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
        className,
      )}
      {...props}
    />
  )
}

export { FilterSelect }
