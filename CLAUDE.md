# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

Relationship Network 是全球人才精准匹配平台：多租户 SaaS，租户通过成员协作维护企业与职位，平台按套餐计费。当前为 MVP 阶段，已实现认证/租户/RBAC/MFA、平台管理、计费与用量、线下订单、企业管理、职位管理（含职位需求解析链路）；人才检索/匹配核心链路正在接入（检索底座）。

- **后端**：Python 3.12 + FastAPI + SQLAlchemy 2.0（asyncpg）+ Pydantic Settings，Poetry 2.3（`package-mode = false`）。
- **异步任务**：Celery 5（Redis broker/result backend），负责邀请邮件、过期预订清扫、订阅过期、LLM 配置探测、职位需求解析等。
- **前端**：Next.js 16（App Router、React 19、TypeScript）+ Tailwind CSS v4 + shadcn/ui + Bun 1.3。
- **基础设施**：PostgreSQL 16（多租户隔离依赖 RLS）、Redis 7、MinIO（私有对象存储）。
- **外部依赖**：OpenRouter（LLM）、检索底座（版本化的人物/论文检索服务，仅服务端消费其契约）。

本仓库还有两份约定文档，工作前应了解其定位：**`CONTEXT.md`** 定义领域语言（术语表 + `_Avoid_` 反义词，写代码前先对齐术语）；**`AGENTS.md`** 是更完整的仓库规范（构建运行、代码风格、测试约定、安全注意事项、Issue 分诊与领域文档协作约定）。架构决策在 `docs/adr/`（001–025），面向 agent 的流程约定在 `docs/agents/`。

## 常用命令

### 启动完整环境（推荐，需 Docker Desktop）

```bash
cp .env.example .env      # 替换占位密码
docker compose up --build -d
docker compose ps         # 等待所有服务 healthy
```

入口：前端 <http://localhost:3000>、API 文档 <http://localhost:8000/docs>、就绪探针 <http://localhost:8000/health/ready>、MinIO 控制台 <http://localhost:9001>。`api` 容器启动时自动执行 `alembic upgrade head`。`docker compose down` 保留数据；`down --volumes` 永久删除 Postgres/Redis/MinIO 数据。

### 不使用 Docker 开发

```bash
# 后端：先 cp backend/.env.example backend/.env 并填本机凭据
cd backend
poetry install --with dev
poetry run uvicorn --app-dir src relationship_network_api.main:create_app --factory --reload

# 前端：另开终端
cd frontend
bun ci
API_INTERNAL_URL=http://localhost:8000 bun run dev
```

### 质量检查（提交前必须全绿）

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

### 运行单个测试

后端用 pytest（`pythonpath = ["src"]`，测试已标记 `integration`）：

```bash
cd backend
poetry run pytest tests/test_auth_service.py -k "login"                    # 按关键字
poetry run pytest tests/test_auth_service.py::TestAuthService::test_x      # 按路径
poetry run pytest tests/integration/test_rls_isolation.py -k "cross"       # 单个集成用例（需真实 Postgres/Redis/MinIO + RN_* 环境变量）
```

前端用 vitest：

```bash
cd frontend
bunx vitest run tests -t "keyword"
```

### 集成与端到端

```bash
# 真实依赖集成测试（需 Postgres/Redis/MinIO + 一致的 RN_* 环境变量）
cd backend && poetry run pytest tests/integration/

# 浏览器端到端（需完整 Compose 环境已启动）
cd frontend/e2e && bun ci && bunx playwright install chrome msedge
bun run test:healthy     # 健康态页面验收（保存截图）
bun run test:degraded    # 降级态（MinIO 停掉后 /health/ready 返回 503）
```

### 数据库迁移

迁移文件在 `backend/migrations/versions/`，0001 起按序编号。**新增迁移必须保证 upgrade→downgrade→upgrade 往返可回滚**（CI 会执行该往返）：

```bash
cd backend
poetry run alembic upgrade head
poetry run alembic downgrade base
poetry run alembic upgrade head
```

## 架构（跨多文件才能看清的"大局"）

### 后端分层

请求经 **routers**（HTTP 层，`routers/*.py`）→ **领域 service**（`*_service.py`）→ **`models.py`**（SQLAlchemy 实体）→ **`deps.py`**（FastAPI 依赖注入与门禁）。业务写路径必须经对应 service（如成员停用/移除只能走 `membership_service`，它拒绝任何针对租户所有者的操作）。配置统一经 `config.py` 的 `AppSettings`（`RN_` 前缀），不要散落 `os.environ`。

### 多租户隔离：PostgreSQL RLS + 数据库角色 + 事务级 GUC

这是贯穿整个系统的安全模型，涉及三个文件：

- **`db.py`**：每个连接池连接建立时 `SET ROLE relationship_app`（非超级用户角色），使 RLS 对所有应用查询生效。另定义了多个受限角色：`relationship_platform_worker`、`relationship_outbox_dispatcher`、`relationship_llm_maintenance`、`relationship_requirement_maintenance`、`relationship_requirement_scheduler`。
- **`tenant_context.py`**：用 `set_config('app.tenant_id', …)` 等在事务内写入 GUC（`app.tenant_id` / `app.user_id` / `app.invite_token_hash` / `app.platform_admin`），由数据库 RLS 策略读取。
- **`deps.py`**：`get_tenant_context` 解析成员关系 → 设租户 GUC → 强制 MFA 策略 → 解析权限 → 返回 `TenantContext`。平台管理的跨租户读取经 `set_platform_admin_context`（`app.platform_admin='on'`）显式放行。

**不要绕过 RLS**；跨租户读取只能通过平台管理员 GUC。审计表（`platform_audit_events` / `tenant_audit_events`）与用量台账（`usage_ledger_entries`）只增不改——应用角色仅有 SELECT/INSERT，禁止为它们写 UPDATE/DELETE 代码。

### Celery 拓扑与角色化 Worker

`tasks.py` 注册任务；`compose.yaml` 把不同队列拆到不同容器，各自带不同 DB 角色：

- **worker**：队列 `celery,platform,tenant`（邀请邮件、预订/订阅清扫、职位需求解析）。
- **llm-maintenance-worker**：队列 `maintenance`（LLM 原始响应清理、需求正文清理等维护路径）。
- **platform-scheduler**：Celery beat（预订清扫每 300s、订阅过期每日）。
- **outbox-dispatcher**：`python -m relationship_network_api.platform_outbox_dispatcher`。

任务内部用 `anyio.run(...)` 跑异步 payload，并自行 `create_engine_from_settings(database_role=…)` 建连接（不共享请求级 session）。

### 持久化异步任务（durable task 模式）

LLM 配置探测与职位需求解析不是一次性 Celery 任务，而是**持久化到数据库的工作单元**：带租约（lease）、心跳、`queued → 执行 → 等待重试 → 取消中 → 成功/失败/冲突/已取消` 状态机，事件经 SSE 回放（`Last-Event-ID` 续播）。`durable_task.py` 提供租约时长、指数退避、SSE 编码等作用域中立的共享原语；具体实现分别在 `llm_configuration_worker.py` 与 `job_requirement_worker.py`。

### 版本化的不可变资产与契约

- **LLM 资产**：`llm_assets/manifest.py` 用 sha256 钉死不可变的 Schema（v1/v2）与提示词资产，`validate_deployed_assets()` 校验哈希漂移。职位需求 Schema 版本冻结可执行条件目录、操作符、结构化输出形态与校验规则。
- **检索底座契约**：`search_base_contract.py` 定义版本化契约（`X-Search-Contract-Version: v1`）、硬条件字段目录（`HARD_CONDITION_FIELD_CATALOG`）与响应模型；`search_base.py` 是带重试/退避的 adapter，并强制校验响应不含联系方式键（`FORBIDDEN_CONTACT_KEYS`）、命中按分数降序、request_id 回显一致。
- 检索底座只提供当前数据版本的读取；规范人物（canonical person）与人物证据是只读外部数据，本产品不持久化为本地人才记录。

### 前端

- **App Router** 路由组：`(auth)`（login/register/invite）与 `(product)`（members/companies/jobs/usage/admin/settings），另有一组扁平路由镜像页面结构。
- **API 访问**：`src/lib/*-client.ts`（ky 封装）+ `*-contract.ts`（zod 校验），页面/Server Action 不直接拼 fetch。
- **`src/middleware.ts`**：会话 Cookie（`rn_session`，HttpOnly）滑动续期。
- **设计系统**：遵循 `docs/adr/0024`（OpenAI 布局规格）；运行时颜色以 `frontend/src/app/globals.css` 为准，组件用 shadcn/ui 语义 token，禁止原始色值。

## Agent 协作约定

（完整规则见 `docs/agents/`；此处只列需要在实际工作中遵守的动作。）

- **Issue 跟踪**：仓库是 `pray4her/relationship_network`（私有）的 GitHub Issues。一个 Issue 对应一个可独立执行的工作单元，正文自包含；行动前读完正文、标签与评论；验收证据记录后才可关闭。外部 PR 不是分诊入口（PR 只走正常 review，不进入分诊状态机）。优先 GitHub connector，`gh` CLI 兜底。
- **分诊标签**：只用五个规范标签 `needs-triage` / `needs-info` / `ready-for-agent` / `ready-for-human` / `wontfix`，不要新建同义重复标签。
- **领域文档**：单上下文仓库——共享领域语言见根目录 `CONTEXT.md`，架构决策见 `docs/adr/`。**提案与已接受的 ADR 冲突时必须显式说明，决定是 supersede 该 ADR 还是调整提案，不要静默绕过。**

## 关键约定（要点）

- **领域语言**：使用 `CONTEXT.md` 定义的术语（租户、成员、企业、职位、职位需求草稿/版本、检索底座、规范人物、人物证据……），不要引入 `_Avoid_` 同义词。新概念无既定术语时视为领域建模缺口，先补术语再写代码。
- **计费写路径**：必须经 `deps.require_writable_tenant` 门禁（订阅到期后租户只读 403 `subscription_read_only`）；用量记账必须用幂等键（同一键不同参数返回 409）。线下订单提交故意不用该门禁（到期租户靠提交订单续费）。
- **平台管理员**：唯一授权来源是 `RN_PLATFORM_ADMIN_EMAILS`，与租户 RBAC 完全隔离；强制 TOTP MFA。
- **测试标记**：需要真实 Postgres/Redis/MinIO 的用例放 `tests/integration/` 并打 `integration` 标记；`filterwarnings = ["error"]` 使警告即失败。
- **Issue 跟踪**：GitHub Issues（`pray4her/relationship_network`），分诊用五个规范标签（`needs-triage` / `needs-info` / `ready-for-agent` / `ready-for-human` / `wontfix`），不要新建同义标签。详见 `docs/agents/issue-tracker.md` 与 `docs/agents/triage-labels.md`。

更完整的仓库规范见 `AGENTS.md`；领域术语全表见 `CONTEXT.md`。
