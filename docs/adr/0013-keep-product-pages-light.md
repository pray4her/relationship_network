# 产品页面保持单一浅色主题

> Status: Claude 表面分层表述被 [ADR 0024](./0024-openai-design-system-via-shadcn-carrier.md) supersede;「产品不启用暗色主题切换」仍有效。

租户与平台管理页面需要稳定、连续的工作表面。产品页面统一使用浅色主题，以 `background`、`muted` 和 `card` 等语义表面建立层级，不使用整页或整段深色反转，也不新增暗色主题或自动主题切换(`.dark` token 可保留于 CSS 结构,但不挂载到产品 UI)。

强调色 `#000000` 承担主要操作、链接、焦点和当前位置，功能色只表达状态。代码、原始文档预览或终端输出等具有真实技术语义的局部表面可用 `muted`/`card` 区分,不再使用 Claude `surface-dark` 命名。
