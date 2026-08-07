# Repository Guidelines

## 项目概览

Relationship Network 是全球人才精准匹配平台的商业产品仓库：多租户 SaaS，租户通过成员协作维护企业档案，平台按套餐计费。当前为 MVP 阶段，已实现认证/租户/RBAC/MFA、平台管理、计费与用量、线下订单、企业管理（含文档上传）、职位管理（含材料上传）等能力；人才检索/匹配核心链路（向量检索等）尚在规划中（见 `deployment_plan.md`）。

技术栈与运行时组件：

- **后端 API**：Python 3.12 + FastAPI + SQLAlchemy 2.0（asyncpg 异步驱动）+ Pydantic Settings，包管理用 Poetry 2.3（`package-mode = false`）。
- **异步任务**：Celery 5（Redis 作 broker 与 result backend），负责邀请邮件、过期预订清扫、订阅过期等。
- **前端**：Next.js 16（App Router、React 19、TypeScript）+ Tailwind CSS v4 + shadcn/ui（`base-nova` 风格）+ Bun 1.3 包管理。
- **基础设施**：PostgreSQL 16（多租户隔离依赖 RLS）、Redis 7、MinIO（私有对象存储，企业文档）。
- **本地与 CI 编排**：根目录 `compose.yaml`（Docker Compose v2）定义全部服务：postgres、redis、minio、minio-init、api、worker、frontend。

目录布局：

```text
/
├── compose.yaml            # 全栈编排，唯一事实源
├── CONTEXT.md              # 领域语言（术语表，含 _Avoid_ 反义词）
├── docs/adr/               # 架构决策记录
├── docs/agents/            # 面向 agent 的流程约定（issue 跟踪、标签、领域文档）
├── backend/
│   ├── src/relationship_network_api/   # 应用代码（扁平模块 + routers/ 子目录）
│   ├── migrations/versions/            # Alembic 迁移，0001 起按序编号
│   └── tests/                          # pytest；tests/integration/ 需真实基础设施
├── frontend/
│   ├── src/app/            # App Router 页面（/login /register /members /companies /jobs /usage /admin /settings /invite）
│   ├── src/components/     # 业务组件 + ui/（shadcn 组件）
│   ├── src/lib/            # API client 与 contract 层（每域一对 *-client.ts / *-contract.ts）
│   ├── src/middleware.ts   # 会话 Cookie 滑动续期
│   ├── tests/              # Vitest + Testing Library 单元测试
│   └── e2e/                # 独立 Bun 工具的 Playwright 测试（真实 Chrome/Edge）
└── shots/                  # 页面验收截图
```

## 构建与运行

完整环境（推荐，需 Docker Desktop）：

```bash
cp .env.example .env   # 替换占位密码
docker compose up --build -d
docker compose ps      # 等待所有服务 healthy
```

访问入口：前端 <http://localhost:3000>，API 文档 <http://localhost:8000/docs>，就绪探针 <http://localhost:8000/health/ready>，MinIO 控制台 <http://localhost:9001>。

- API 容器启动时自动执行 `alembic upgrade head`。
- `docker compose down` 保留数据卷；`down --volumes` 会永久删除 PostgreSQL/Redis/MinIO 数据。
- Celery beat 独立于 worker：`docker compose exec worker poetry run celery -A relationship_network_api.tasks:celery_app beat --loglevel=INFO`（预订清扫每 300 秒触发一次）。
- Worker 冒烟验证：`docker compose exec worker poetry run python -c "from relationship_network_api.tasks import smoke; print(smoke.delay('manual-smoke').get(timeout=10))"`。

不使用 Docker 的开发方式：

```bash
# 后端（Python 3.12 + Poetry 2.3），先 cp backend/.env.example backend/.env 并填本机凭据
cd backend && poetry install --with dev
poetry run uvicorn --app-dir src relationship_network_api.main:create_app --factory --reload

# 前端（Bun 1.3）
cd frontend && bun ci
API_INTERNAL_URL=http://localhost:8000 bun run dev
```

## 质量检查（提交前必须全绿）

```bash
# 后端
cd backend
poetry run ruff check .
poetry run ruff format --check .
poetry run basedpyright
poetry run pytest -m "not integration"

# 前端
cd frontend
bun run lint        # biome check
bun run typecheck   # tsc --noEmit
bun run test        # vitest run
bun run build       # next build
```

端到端（需完整 Compose 环境已启动）：

```bash
cd frontend/e2e
bun ci && bunx playwright install chrome msedge
bun run test:healthy     # 健康态页面验收（保存截图）
bun run test:degraded    # 降级态（MinIO 停掉后 /health/ready 返回 503 的场景）
```

真实依赖集成测试（需 PostgreSQL/Redis/MinIO 及一致的 `RN_*` 环境变量）：

```bash
cd backend && poetry run pytest tests/integration/
```

## 代码风格

后端（`backend/pyproject.toml` 为准）：

- Ruff `select = ["ALL"]`，行宽 100，双引号，Google docstring 约定；测试目录放行 ARG/D/PLR2004/S101 等规则。
- basedpyright `typeCheckingMode = "all"`（对 Any/Unknown 等放宽，见配置）。
- pytest 开启 `--strict-config --strict-markers` 且 `filterwarnings = ["error"]`——警告即失败。
- 分层：routers（HTTP 层）→ 领域 service（`*_service.py`）→ `models.py`（SQLAlchemy）→ `deps.py`（依赖注入与门禁）。业务变更必须走对应 service（例如成员停用/移除只能经 `membership_service`，它拒绝任何针对租户所有者的操作）。
- 配置统一经 `config.py` 的 `AppSettings` 读取 `RN_` 前缀环境变量，不要散落 `os.environ`。

前端（`frontend/biome.json` 为准）：

- Biome 2 统一 lint+format：2 空格缩进、双引号、行宽 100、`noExplicitAny`、`noNonNullAssertion`、`useImportType` 均为 error。
- 组件复用 `components.json` 中的别名（`@/components`、`@/components/ui`、`@/lib`）与 shadcn/ui 主题约定；不要新建与 `ui/` 重复的基元组件。
- API 访问走 `src/lib/` 的 `*-client.ts`（ky 封装）+ `*-contract.ts`（zod 校验），页面/Server Action 不直接拼 fetch。
- 视觉系统遵守 ADR `docs/adr/0001`：暖米白底、近黑文字、陶土橘 `#d97757` 为唯一强调色，仅浅色主题；token 以 `src/app/globals.css` 为唯一事实源。

领域语言：使用 `CONTEXT.md` 定义的术语（租户、成员、企业、邀请、两步验证、套餐订单、平台健康状态……），不要引入 `_Avoid_ 列出的同义词`。新概念没有约定术语时视为领域建模缺口，先补术语再写代码。

## 测试约定

- 后端单元测试在 `backend/tests/`，与模块一一对应（`test_<area>_service.py` / `test_<area>_routes.py`）；需要真实 PostgreSQL/Redis/MinIO 的用例放 `tests/integration/` 并打 `integration` 标记。
- 前端单元测试在 `frontend/tests/`（Vitest + Testing Library + jsdom），浏览器验收在 `frontend/e2e/`（Playwright，真实 Chrome 与 Edge）。
- CI（`.github/workflows/ci.yml`）分三个 job：`backend`（lint/类型/单测/迁移 upgrade→downgrade→upgrade 往返）、`frontend`（lint/类型/单测/生产构建）、`compose`（全栈启动后跑依赖探针、Celery 冒烟、健康与降级两条 Playwright 链路）。新增迁移必须保证往返可回滚。

## 安全注意事项

- 会话通过 HttpOnly Cookie `rn_session` 维持，数据库只存令牌的 SHA-256 哈希；登录失败统一返回 401 `invalid_credentials`，不区分邮箱不存在与密码错误。
- 多租户隔离依赖 PostgreSQL RLS；跨租户的平台管理读取必须经 `app.platform_admin` GUC 显式放行，不要绕过。
- 平台管理员身份的唯一授权来源是 `RN_PLATFORM_ADMIN_EMAILS` 环境变量，与租户 RBAC 完全隔离；平台管理员强制 TOTP MFA。
- 审计表（`platform_audit_events`、`tenant_audit_events`）与用量台账（`usage_ledger_entries`）为只增不改：应用角色仅有 SELECT/INSERT，更新与删除由数据库权限拒绝——不要为这些表写 UPDATE/DELETE 代码。
- 计费写路径必须经 `deps.require_writable_tenant` 门禁（订阅过期后租户只读）；用量记账必须用幂等键（同一键不同参数返回 409）。
- 密钥管理：`.env` 不入库，模板是 `.env.example` / `backend/.env.example`；生产环境应设 `RN_SESSION_COOKIE_SECURE=true`。企业文档仅存私有 MinIO 桶，下载走鉴权流式接口，无公开 URL。

## Agent 协作约定

### Issue 跟踪

Issue 与 PRD 跟踪在私有仓库 `pray4her/relationship_network` 的 GitHub Issues。优先使用 GitHub connector 操作，`gh` CLI 作为兜底（从 git remote 推断仓库）。外部 PR 不是分诊入口。详见 `docs/agents/issue-tracker.md`。

约定：一个 Issue 对应一个可独立执行的工作单元；正文自包含，不要求 agent 从聊天记录还原需求；行动前读完正文、标签与评论；验收证据记录后才可关闭。

### 分诊标签

使用五个规范标签：`needs-triage`、`needs-info`、`ready-for-agent`、`ready-for-human`、`wontfix`。不要创建同义重复标签。详见 `docs/agents/triage-labels.md`。

### 领域文档

单上下文仓库：共享领域语言见根目录 `CONTEXT.md`，架构决策见 `docs/adr/`。提案与已接受的 ADR 冲突时必须显式说明，决定是 supersede ADR 还是调整提案，不要静默绕过。详见 `docs/agents/domain.md`。
