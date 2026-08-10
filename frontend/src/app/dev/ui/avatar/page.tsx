import { UserRoundIcon } from "lucide-react"

import {
  Avatar,
  AvatarBadge,
  AvatarFallback,
  AvatarGroup,
  AvatarGroupCount,
  AvatarImage,
} from "@/components/ui/avatar"

import { PreviewPage, PreviewSection } from "../_preview"

const sizes = ["xs", "sm", "default", "lg", "xl"] as const
const statuses = ["online", "offline", "busy", "away"] as const

export default function AvatarPreviewPage() {
  return (
    <PreviewPage
      description="尺寸、图片回退、姓名首字母、通用图标、在线状态与交互态均来自 avatar.css。"
      title="Avatar"
    >
      <PreviewSection title="尺寸与回退">
        <div className="flex flex-wrap items-end gap-[var(--space-6)]">
          {sizes.map((size) => (
            <div className="grid justify-items-center gap-[var(--space-2)]" key={size}>
              <Avatar aria-label={`${size} 姓名头像`} size={size} variant="initials">
                <AvatarFallback>RN</AvatarFallback>
              </Avatar>
              <span className="font-mono text-[length:var(--text-caption)] text-muted-foreground">
                {size}
              </span>
            </div>
          ))}
          <Avatar aria-label="通用成员头像" size="lg" variant="generic">
            <AvatarFallback>
              <UserRoundIcon />
            </AvatarFallback>
          </Avatar>
          <Avatar aria-label="图片加载失败后的回退" size="lg" variant="initials">
            <AvatarImage alt="" src="/missing-avatar.png" />
            <AvatarFallback>张</AvatarFallback>
          </Avatar>
        </div>
      </PreviewSection>

      <PreviewSection title="状态与组合">
        <div className="flex flex-wrap items-center gap-[var(--space-6)]">
          {statuses.map((status) => (
            <Avatar aria-label={`成员，${status}`} key={status} size="lg" variant="initials">
              <AvatarFallback>{status.slice(0, 1).toUpperCase()}</AvatarFallback>
              <AvatarBadge status={status} />
            </Avatar>
          ))}
          <AvatarGroup aria-label="协作成员">
            <Avatar size="sm" variant="initials">
              <AvatarFallback>林</AvatarFallback>
            </Avatar>
            <Avatar size="sm" variant="initials">
              <AvatarFallback>陈</AvatarFallback>
            </Avatar>
            <AvatarGroupCount>+3</AvatarGroupCount>
          </AvatarGroup>
          <Avatar
            aria-label="打开账户菜单"
            interactive
            render={<button type="button" />}
            size="lg"
            variant="initials"
          >
            <AvatarFallback>账</AvatarFallback>
          </Avatar>
        </div>
      </PreviewSection>
    </PreviewPage>
  )
}
