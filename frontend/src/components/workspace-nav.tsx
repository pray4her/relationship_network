import Link from "next/link"

type WorkspaceNavProps = {
  readonly permissions: readonly string[]
  readonly isPlatformAdmin: boolean
}

export function WorkspaceNav({ isPlatformAdmin, permissions }: WorkspaceNavProps) {
  return (
    <nav className="workspace-nav" aria-label="工作区">
      <Link className="workspace-nav-link" href="/">
        首页
      </Link>
      {permissions.includes("members:read") ? (
        <Link className="workspace-nav-link" href="/members">
          成员
        </Link>
      ) : null}
      {permissions.includes("billing:read") ? (
        <Link className="workspace-nav-link" href="/usage">
          用量与套餐
        </Link>
      ) : null}
      <Link className="workspace-nav-link" href="/settings/security">
        安全设置
      </Link>
      {isPlatformAdmin ? (
        <Link className="workspace-nav-link" href="/admin">
          平台管理
        </Link>
      ) : null}
    </nav>
  )
}
