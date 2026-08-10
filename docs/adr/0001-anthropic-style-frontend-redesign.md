# 前端视觉系统采用 Anthropic 气质(shadcn + Tailwind v4 承载)

> Status: 部分条款被 [ADR 0003](./0003-claude-design-system-via-shadcn-carrier.md) supersede(唯一强调色、自托管字体);载体、仅浅色主题、语义 token 硬约束仍有效。

前端从手写 BEM CSS 的粗野主义风格(荧光绿、网格背景、全直角描边)全量重构为 Anthropic 官网气质:暖米白 `#faf9f5` 底、近黑 `#141413`、陶土橘 `#d97757` 单强调色、仅浅色主题。token 经 shadcn CSS variables + Tailwind v4 `@theme inline` 承载,组件全部替换为 shadcn 注册表版本,页面标记用 Tailwind 工具类重写。

## Considered Options

- **忠实复刻 anthropic-DESIGN.md 全部 token(含 12px 正文、单断点)**:被否。该文件抓取自营销官网,直接套用到数据密集型中文后台会牺牲可用性;改为借其调色板/圆角/阴影/动效,字号与断点按后台需求调整。
- **严格纯两色、零强调色**:被否。后台的 CTA、链接、当前导航需要辨识度;取 Anthropic 实际品牌陶土橘作为唯一强调色,状态语义用低饱和功能色。
- **CDN 加载 Anthropic 字体**:被否。jsDelivr 运行时可用性不可控;改为 woff2 自托管 + `next/font/local`。
- **保留手写 CSS、仅 Tailwind 换皮**:被否。双样式体系并存必然腐化;769 行 BEM 全量删除,token 以 globals.css 为唯一事实源。

## Consequences

- Anthropic Sans/Mono 来自第三方再分发仓库(dqev/fonts),存在许可不确定性,商用发布前必须确认授权。所得 woff2 实为可变字体(wght 300–800,Sans 另带 opsz 轴),故每族只自托管单文件,经 `next/font/local` 以字重区间注册。
- 仅浅色主题为明确决策,不是遗漏;token 结构保留了日后加暗色的扩展位,但不许在组件里手写 `dark:` 覆盖。
- 组件内只允许语义 token(`bg-primary`、`text-muted-foreground`),禁止原始色值——这是写代码的硬约束,不是风格建议。
