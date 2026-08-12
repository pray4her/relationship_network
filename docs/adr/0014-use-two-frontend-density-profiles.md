# 前端采用产品与入口两档信息密度

> Note: 视觉 token 已切至 [ADR 0024](./0024-openai-design-system-via-shadcn-carrier.md)(OpenAI / 8px 网格);两档拨盘数值仍有效。

租户与平台管理页面以持续操作和数据扫描为主，采用 `DESIGN_VARIANCE 4 / MOTION_INTENSITY 2 / VISUAL_DENSITY 7`；登录、注册、邀请和平台健康页采用 `DESIGN_VARIANCE 5 / MOTION_INTENSITY 3 / VISUAL_DENSITY 4`。两档共享同一 token、原语和品牌语言，只调整构图、间距与内容密度。

产品页面使用 8px 网格上的 24-32px 主要节奏。动效只用于导航菜单、Overlay、状态切换和操作反馈，并为 reduced-motion 提供静态或即时降级。
