import Image from "next/image"

import { cn } from "@/lib/utils"

type BrandMarkProps = {
  readonly className?: string
  readonly compact?: boolean
}

/** 可替换的品牌组合；更换图标时不影响 Navbar 或 AuthShell 合同。 */
export function BrandMark({ className, compact = false }: BrandMarkProps) {
  return (
    <span className={cn("inline-flex min-w-0 items-center gap-[var(--space-2)]", className)}>
      <Image
        alt=""
        aria-hidden="true"
        className="size-[var(--brand-mark-size)] shrink-0"
        height={24}
        priority
        src="/icon.svg"
        unoptimized
        width={24}
      />
      {compact ? null : (
        <span className="truncate font-display text-[length:var(--text-title-md)] leading-[var(--text-title-md--line-height)] font-normal text-foreground">
          Relationship Network
        </span>
      )}
    </span>
  )
}
