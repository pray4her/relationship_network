# 使用仓库内 Copernicus 与 StyreneB 字体文件

前端使用 `frontend/src/app/fonts/` 中已获准正式部署的 Copernicus Book、StyreneB Regular 与 StyreneB Medium 文件，通过 `next/font/local` 自托管并映射到现有字体 CSS variables。Copernicus Book 只用于品牌与页面主标题，StyreneB Regular 对应正文 400，StyreneB Medium 对应产品标题、标签、导航和按钮 500。

字体加载失败时保留现有 serif 与 sans 系统 fallback。`--font-mono` 继续使用 JetBrains Mono 与系统等宽 fallback，不把本机安装状态视为生产依赖。
