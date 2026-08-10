# 使用 Route Groups 集中管理前端外壳

前端通过不改变 URL 的 Next.js Route Groups 集中管理页面外壳：`(product)` 的共享 Layout 提供 AppShell、Navbar、主内容 landmark 与产品页容器，`(auth)` 的共享 Layout 提供低密度 AuthShell，`dev` 继续独立并在生产环境返回 404。根 Layout 只保留全局 HTML、字体、metadata 和全局反馈挂载点。

产品路由、认证路由、Server Action 目标和外部链接保持不变。现有各页面及错误分支重复渲染的 AccountPanel 将被移除，平台管理模式提示由产品外壳统一呈现。
