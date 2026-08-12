import Image from "next/image"

import { cn } from "@/lib/utils"

type BrandMarkProps = {
  readonly className?: string
  readonly compact?: boolean
}

/** 可替换的品牌组合；更换图标时不影响 Navbar 或 AuthShell 合同。 */
export function BrandMark({ className, compact = false }: BrandMarkProps) {
  return (
    <span className={cn("inline-flex min-w-0 items-center gap-2", className)}>
      <Image
        alt=""
        aria-hidden="true"
        className="size-5 shrink-0"
        height={20}
        priority
        src="/icon.svg"
        unoptimized
        width={20}
      />
      {compact ? null : (
        <span className="truncate text-base font-semibold leading-normal text-foreground">
          Relationship Network
        </span>
      )}
    </span>
  )
}
