# 前端视觉系统切换至 OpenAI 测量规格(supersede ADR 0003 相应条款)

前端视觉规格改以 `docs/openai-DESIGN.md` 的布局骨架(system-ui、8px 网格、5px 圆角、400ms ease)+ `frontend/src/app/globals.css`(运行时唯一事实源)为准,载体仍为 shadcn/ui base-nova + Tailwind v4。**产品覆盖测量色**:主色与正文均为 `#000000`,on-primary 为 `#ffffff`;次要文案用 muted 灰阶。产品不启用暗色主题切换(`.dark` token 仅保留结构兼容)。**退役** Claude `frontend/showcase/`、`frontend/src/styles/tokens.css` 与组件 CSS、Copernicus/StyreneB 自托管字体。

**ADR 0003 中被 supersede 的条款**:showcase + tokens.css 唯一标准、珊瑚橘 `#cc785c` primary、多强调色、Copernicus/StyreneB、token 双文件同步纪律。**仍然有效的条款**:shadcn + Tailwind v4 为载体、组件内只允许语义 token、禁止双样式体系并存于运行时、按消费者补齐 UI 原语(ADR 0017)。

**一并 supersede**:ADR 0001 残留暖米白/陶土橘视觉条款;ADR 0011 衬线展示字体限制;ADR 0020 Copernicus/StyreneB 自托管;ADR 0013 中 Claude 表面分层(`surface-soft`/`card` 奶油层级)表述——保留「产品页不启用暗色切换」。

## Considered Options

- **严格沿用 openai-DESIGN 测量正文/主色 `#8e8ea0`**:曾采纳后因可读性不足被产品决策覆盖为 `#000000`。
- **启用 `.dark` 主题切换**:被否。产品页需要稳定浅色工作面;保留 `.dark` 变量块仅兼容 shadcn 结构。
- **保留 Claude showcase 作并行对照**:被否。双规格并存必然腐化,与 ADR 0001/0003 否决双体系的逻辑一致。

## Consequences

- `globals.css` 为唯一运行时事实源;布局/间距/字号骨架参考 `docs/openai-DESIGN.md`,颜色以产品覆盖值为准。
- 页面与布局原语改用标准语义 token(`bg-background`、`text-foreground`、`gap-*`、`rounded-[var(--radius)]`),不再依赖 `--space-*`/`--text-display-*`/`font-display` 等 Claude 扩展。
- ADR 0014 两档密度保留,节奏改为 8px 网格;产品页标题用 Heading(32/600),认证与首页可用 Display(48/700)。
