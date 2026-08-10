# 前端 UI 重构计划

> 状态：待最终确认。本文记录完整的执行基线；在双方确认已经形成共同理解前，不开始实现。

## 目标

在不改变现有 URL、导航信息架构、权限门禁、业务流程、Server Action 与表单字段合同的前提下，使用 Claude 视觉规格、语义 token、shadcn/Base UI 原语和共享页面构图原语，全面重构前端应用外壳、页面排版、响应式布局与状态呈现。

## 已确认的架构与视觉约束

- [ADR 0009](adr/0009-preserve-frontend-information-architecture.md)：保留信息架构与交互合同，只重构表现层。
- [ADR 0010](adr/0010-use-top-navbar-for-frontend-shell.md)：桌面使用顶部 Navbar，移动端使用同一导航源的折叠菜单。
- [ADR 0011](adr/0011-limit-display-serif-to-page-titles.md)：衬线展示字体只用于品牌与页面主标题。
- [ADR 0012](adr/0012-use-flat-page-composition.md)：产品页面采用平面构图，Card 只用于真实独立容器。
- [ADR 0013](adr/0013-keep-product-pages-light.md)：产品页面保持单一暖米白浅色主题。
- [ADR 0014](adr/0014-use-two-frontend-density-profiles.md)：产品与入口页面使用两档信息密度。
- [ADR 0015](adr/0015-mark-platform-admin-context-in-shared-shell.md)：共享外壳持续标记平台管理上下文。
- [ADR 0016](adr/0016-keep-semantic-tables-on-small-screens.md)：小屏继续使用语义 Table。
- [ADR 0017](adr/0017-add-ui-components-only-for-current-consumers.md)：UI 原语按当前页面消费者补齐。
- [ADR 0018](adr/0018-centralize-frontend-shells-with-route-groups.md)：使用 Route Groups 集中管理产品与认证外壳。
- [ADR 0019](adr/0019-compose-pages-from-small-layout-primitives.md)：页面由小型组合式布局原语构成。
- [ADR 0020](adr/0020-use-provided-copernicus-and-styreneb-font-files.md)：使用仓库内 Copernicus 与 StyreneB 字体文件。

## 已确认的状态反馈模型

- 主要数据页面提供与最终结构一致的 `loading.tsx`，使用 Skeleton，不使用居中的通用 Spinner。
- 空数据使用 Empty，解释空状态，并在成员具备权限时提供明确操作。
- 读取失败在所属 DataRegion 内使用 Alert，保留页面上下文。
- 字段错误显示在字段下方，表单级错误使用相邻 Alert。
- Server Action 按钮使用 Button loading，统一 disabled、aria-busy 与加载视觉。
- 跳转或刷新后的新页面状态承担成功反馈，不重复弹出 Toast。
- Sonner 只服务无法自然落在内容区的短暂反馈；没有真实消费者时不挂载。
- 破坏性操作继续使用 AlertDialog 明确确认。

## 已确认的文案边界

- 允许优化页面说明、空状态、错误、加载、权限与只读提示，使文案简洁并包含可执行的下一步。
- 删除 `ACCOUNT / 账户` 等装饰性双语眉题，不增加营销套话、无依据承诺或装饰性英文。
- 保留 Navbar 信息架构、表单字段名称与顺序、法律安全含义和业务合同。
- 严格使用 `CONTEXT.md` 领域术语；移除现有 `WorkspaceNav` 与 `aria-label="工作区"` 中被 glossary 禁止的“工作区”称呼。
- 按钮使用具体动作，状态名称、中文标点、数字、金额和时间格式保持一致。
- 页面可见文案不使用装饰性破折号。

## 已确认的品牌资产边界

- Navbar、Favicon 与认证页面使用现有 `frontend/src/app/icon.svg` 网络节点图标和 `Relationship Network` 字标。
- 不使用或模仿 Anthropic 的放射状标志；Claude 只提供视觉语言参考，不提供本项目品牌资产。
- Navbar 通过可替换的 BrandMark 组合品牌图标，后续替换图标不改变导航、布局或页面合同。
- 功能图标继续使用项目现有 Lucide 图标族，单个页面不混用第二套功能图标。

## 已确认的迁移批次

1. 冻结当前 19 个 UI 原语、token、showcase、dev 预览和 parity 工具为独立基础提交，不混入页面重构或其他领域改动。
2. 按真实消费者补齐 Navbar、Avatar、Checkbox、RadioGroup、Breadcrumb 及对应预览与 parity 证据。
3. 建立 Route Groups、字体、AppShell、AuthShell、Navbar 和平台管理模式提示，先统一外壳，不同时重排全部页面内容。
4. 建立 PageHeader、PageSection、PageToolbar、DataRegion、DescriptionList、FormSection 和 AuthPanel，并为结构合同提供测试。
5. 依次迁移认证与健康页、企业与职位、成员与用量及安全设置、平台管理页面。
6. 统一 Skeleton、Empty、Button loading、语义 Badge、Select 和移动 Table 列优先级。
7. 执行完整静态、单元、构建、Compose、浏览器、parity 与截图验收。

每一批保持相关质量门禁全绿并形成独立可回滚提交。当前工作树中的其他领域文档与业务改动不并入前端重构提交。

## 已确认的浏览器与截图验收

- 页面重构必须经过真实 Compose 数据与可重复场景驱动的浏览器验收，不能只依据静态代码推断视觉结果。
- 组件级继续使用 `scripts/ui-parity.ts`，将规格图与实现图成对输出到 `test-results/ui-parity/`，由人工复核；不设置像素级自动差异门禁。
- 生产页面的主要验收截图保存到根目录 `shots/`。全部生产路由覆盖桌面与移动端，关键高密度路由额外覆盖 1024 px 宽度。
- Chrome 作为主要截图基准；Chrome 与 Edge 都执行端到端交互兼容性验收。
- 场景至少覆盖正常、加载、空数据、读取失败、无权限、租户只读、平台管理模式与移动 Navbar 展开状态；仅对实际支持该状态的页面取证。
- 人工视觉复核重点检查本地字体是否实际加载、信息层级、溢出、Table 横向滚动、焦点可见性、按钮文案换行与触控目标。
- 截图和人工复核属于发布前必做验收，但不以脆弱的逐像素一致性阻断合并。

## 已确认的响应式与可访问性验收

- 以 WCAG 2.2 AA 为实现目标和内部验收基线，但不宣称已通过第三方正式认证。
- 固定检查 320、390、768、1024 与 1440 px 视口；除语义 Table 的受控横向滚动外，页面不得出现水平溢出。
- 在浏览器 200% 缩放下，内容不得相互遮挡，关键信息和操作入口不得丢失。
- 核心流程必须支持 `Tab`、`Shift+Tab`、`Enter`、`Space` 与 `Escape`；焦点始终清晰可见。
- Dialog 与移动 Navbar 必须约束焦点，并在关闭后将焦点归还给触发控件。
- Landmark、标题层级、表单标签、帮助与错误关联、`aria-current` 和异步状态播报必须具有正确语义。
- 文本、交互控件与焦点样式达到 AA 对比度；状态和错误不得只依赖颜色表达。
- 可点击或可触摸目标原则上不小于 44 x 44 px；如受 Table 密度限制，扩大可交互区域而非仅放大图标。
- Chrome 与 Edge 均执行键盘验收；登录、移动导航、表单错误、Dialog 和高密度 Table 流程额外执行屏幕阅读器抽查。

## 已确认的页面原型与路由映射

页面原型只定义构图和验收预期，由已确认的小型布局原语组合而成；不得形成承载权限、数据读取或业务分支的万能页面组件。

- 概览页：`/`。在产品外壳中呈现平台健康状态与当前账户信息。
- 认证流程页：`/login`、`/login/mfa`、`/register`、`/invite/[token]`。使用独立 AuthShell，其中邀请页保留令牌验证和接受流程。
- 数据集合页：`/companies`、`/jobs`、`/members`、`/admin`、`/admin/orders`。由 PageHeader、PageToolbar 与一个或多个 DataRegion 组成。
- 实体详情页：`/companies/[id]`、`/jobs/[id]`、`/admin/tenants/[id]`。使用 Breadcrumb、DescriptionList、分区操作和相关数据 Table。
- 用量分析页：`/usage`。保留高密度指标、筛选与明细 Table，不套用营销式大数字卡片墙。
- 设置表单页：`/settings/security`。按职责使用 FormSection 分组，保持两步验证的安全语义与流程顺序。
- `/` 继续属于登录后的产品外壳；认证和邀请路由属于 AuthShell。
- `/admin` 路由族复用集合页或详情页构图，同时持续显示“平台管理模式”上下文。

## 已确认的自动化测试门禁

- 每个迁移批次完成后运行前端 `bun run lint`、`bun run typecheck`、`bun run test` 与 `bun run build`，全绿后才形成该批独立提交。
- 新增 UI 原语使用 Vitest 与 Testing Library 验证状态、键盘行为、ARIA 和既有 props 合同，不使用像素断言。
- Navbar 自动化验证桌面与移动端使用同一导航源、当前项标记、账户菜单、平台管理模式提示和焦点归还。
- 页面布局原语只测试语义结构与组合合同，不为视觉结构创建大范围 DOM snapshot。
- 每个迁移页面验证权限重定向、数据读取、Server Action 接线和表单字段合同未发生非预期变化。
- Playwright 为全部生产路由提供与其访问边界相符的访客态或登录态 smoke test。
- 关键业务流程覆盖认证、邀请、成员、企业与文档、职位与材料、用量、两步验证、套餐订单和平台管理。
- 保留平台健康态与 MinIO 降级态测试；业务 E2E 使用真实 Compose 环境和可重复准备的测试数据。
- Chrome 与 Edge 都验证交互兼容性；计划内的主要验收截图只由 Chrome 生成。
- 不设置脱离现有基线的全局覆盖率数字、整页 DOM snapshot 或像素差异自动门禁；自动化重点是行为、语义和业务合同。

## 完成定义

- 19 个既有 UI 原语及新增的当前消费者原语都符合视觉规格、markup 合同、交互状态与 parity 取证要求。
- 15 个生产路由全部迁移到确认的外壳、页面原型、字体、语义 token 和状态反馈模型。
- 保留原 URL、导航信息架构、权限门禁、业务流程、数据合同、Server Action 与表单字段合同。
- 响应式、键盘、屏幕阅读器抽查、Chrome、Edge、真实 Compose 场景和人工截图复核全部完成。
- 前端静态检查、类型检查、单元测试、生产构建和适用的 E2E 全绿。
- 各迁移批次保持独立、可回滚，且不包含当前工作树中的无关领域改动。
