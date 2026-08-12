# 前端视觉系统切换至 Claude 设计体系(showcase 为规格,supersede ADR 0001 相应条款)

> Status: 视觉规格条款被 [ADR 0024](./0024-openai-design-system-via-shadcn-carrier.md) supersede(OpenAI 测量规格 + globals.css 单事实源);shadcn + Tailwind v4 载体、语义 token、禁止双样式体系仍有效。

前端视觉规格改以 `frontend/showcase/`(静态 HTML)+ `frontend/src/styles/`(tokens.css 与 40 个组件 CSS)为唯一标准:primary 从近黑 `#141413` 改为珊瑚橘 `#cc785c`,接受多强调色(accent-teal/accent-amber/图表色),字体栈切到 Copernicus(衬线展示)/StyreneB(sans)/JetBrains Mono 的 fallback 链。**ADR 0001 中被 supersede 的条款**:`#d97757` 为唯一强调色、自托管第三方再分发的 Anthropic Sans/Mono(其许可不确定性随之解除);**仍然有效的条款**:shadcn + Tailwind v4 为载体、仅浅色主题、组件内只允许语义 token、禁止双样式体系并存于运行时。保留载体的理由是 ADR 0001 否决"双体系并存"的逻辑依然成立,本次只换风格不换架构,避免第二次全量重写。

## Considered Options

- **放弃 Tailwind/cva,改用 styles/*.css 纯 CSS 类体系全量重写**:被否。视觉可 1:1 还原 showcase,但等于推翻 ADR 0001 的载体决策,全部页面标记重写,工作量翻倍,且重新引入"两套组件实现"的腐化路径。
- **`globals.css` 直接 `@import` tokens.css 保持单文件事实源**:被否(决策者明确选择)。改为 token 值人工复制进 `globals.css`,tokens.css 作上游规格文档。
- **提前把新体系全部 40 个组件实现为 ui/ 原语**:被否。只重样式化现有 19 个原语,新组件等有功能需求时再按 showcase 规格添加,避免无消费者的投机组件。

## Consequences

- **token 双文件同步纪律**:规格改动先落 `frontend/src/styles/tokens.css`,再人工同步到 `frontend/src/app/globals.css`(app 运行时唯一事实源);两者不许单方面漂移。这是对本 ADR 被否选项的补偿性纪律,违反即回到 ADR 0001 反对的双事实源腐化。
- 组件规格冲突时视觉一律以 showcase 为准;组件 props(现名,如 sonner/field/empty/alert-dialog)尽量不动,内部 cva 类映射到新规格,无对应规格的 variant/size 删除或就近映射。
- 页面标记不重写:Tailwind 默认字号阶梯在 `@theme` 中重映射到新刻度度量,另增 `display-*`/`title-*`/`caption` 命名工具类;商业字体(Copernicus/StyreneB)不可自托管,走 fallback 链。
- 迁移分四期顺序 PR:①globals.css 全量换值+本 ADR;②19 个 ui 原语逐个对齐 showcase;③业务组件与页面;④重生成 `shots/` 与 e2e 截图基线。验收为组件级与 showcase 并排截图人工比对 + `test:healthy` 重生成页面截图,不引入像素 diff 基建。
