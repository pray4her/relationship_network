# Relationship Network

全球人才精准匹配平台的商业产品仓库。当前 MVP 工程骨架包含 FastAPI API、Celery Worker、Next.js 前端、PostgreSQL、Redis 和 MinIO。

## 本地启动（Windows / Linux）

前置条件：Docker Desktop（Compose v2）。首次启动必须复制环境变量模板并替换其中的本地占位密码。

PowerShell：

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

Bash：

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
```

所有服务显示 `healthy` 后访问：

- 前端健康页：<http://localhost:3000>
- API 文档：<http://localhost:8000/docs>
- API 就绪状态：<http://localhost:8000/health/ready>
- MinIO 控制台：<http://localhost:9001>

验证 Worker 冒烟任务：

```powershell
docker compose exec worker poetry run python -c "from relationship_network_api.tasks import smoke; print(smoke.delay('manual-smoke').get(timeout=10))"
```

停止容器但保留数据：

```powershell
docker compose down
```

`docker compose down --volumes` 会永久删除本地 PostgreSQL、Redis 和 MinIO 数据卷，请仅在明确需要重建空环境时使用。

## 数据库迁移

API 容器启动时自动执行 `alembic upgrade head`。在本地开发数据库验证当前基线的升级和回滚：

```powershell
docker compose exec api poetry run alembic downgrade base
docker compose exec api poetry run alembic upgrade head
```

## 不使用 Docker 开发

后端要求 Python 3.12 和 Poetry 2.3。先从仓库根目录创建后端配置，将其中占位值改为本机基础设施凭据，再启动服务：

```powershell
Copy-Item backend/.env.example backend/.env
Push-Location backend
poetry install --with dev
poetry run uvicorn --app-dir src relationship_network_api.main:create_app --factory --reload
Pop-Location
```

前端要求 Bun 1.3：

```powershell
Push-Location frontend
bun ci
$env:API_INTERNAL_URL = "http://localhost:8000"
bun run dev
Pop-Location
```

Bash：

```bash
cd frontend
bun ci
API_INTERNAL_URL=http://localhost:8000 bun run dev
```

## 认证与租户

注册、登录和会话续期由后端 API 提供，会话通过名为 `rn_session` 的 HttpOnly Cookie 维持（Path=/、SameSite=Lax，Secure 由配置决定；数据库只保存令牌的 SHA-256 哈希）。

- `POST /auth/register`：创建用户、租户、owner 成员关系和 14 天试用订阅（单事务），返回 201 及 `{user, tenant, role}`，并种下会话 Cookie。邮箱重复返回 409 `email_already_registered`。未提供 `tenant_name` 时默认使用 `"{display_name} 的租户"`。
- `POST /auth/login`：返回与注册相同的 JSON 结构并种下 Cookie。邮箱不存在与密码错误统一返回 401 `invalid_credentials`，不区分原因。
- `POST /auth/logout`：删除服务端会话并以 `Max-Age=0` 清除 Cookie，无会话时也返回 204。
- `GET /auth/me`：返回当前身份；未认证返回 401 `not_authenticated`。剩余有效期进入续期窗口时自动滑动续期并重写 Cookie。
- `GET /tenants/current`：返回当前租户 `{id, name, slug, role}`；无有效成员关系返回 403。

成员关系可由两条路径写入：注册流程（只创建租户所有者），以及邀请流程——注册时传入 `invite_token`，或已登录后调用 `POST /invitations/accept` 加入租户（同一用户同时只能持有一个活跃成员关系，冲突返回 409 `already_in_tenant`）。成员的停用、启用、移除由 `POST /members/{id}/deactivate`、`POST /members/{id}/activate`、`DELETE /members/{id}` 提供，停用、降级、移除等变更必须经过 `membership_service`：该模块拒绝任何针对租户所有者的此类操作（并有对应单元测试），启用前还会校验用户在其他租户没有活跃成员关系。邀请接口需要 `members:invite` 权限，租户设置（如 MFA 策略）需要 `tenant:manage` 权限。

MFA 基于 TOTP：`POST /auth/mfa/setup` 生成密钥，`POST /auth/mfa/enable` 校验并启用（同时下发一次性恢复码），登录后由 `POST /auth/mfa/verify` 完成二次校验。租户开启 `mfa_required` 后，`get_tenant_context` 会拒绝未完成 MFA 的成员，返回 403 `mfa_required`。

## 平台管理

平台管理员是与租户权限完全隔离的运营身份：其授权边界不经过租户 RBAC，普通租户角色无法获得或推导出该权限。`RN_PLATFORM_ADMIN_EMAILS`（逗号分隔的邮箱名单）是唯一授权来源——名单内邮箱在注册或登录时自动获得 `is_platform_admin` 标记，移出名单后在下一次认证时被回收。平台管理员注册时不会自动创建租户或成员关系（`tenant` / `role` 为 null），也不会以成员身份污染任何租户。

平台管理员必须启用 TOTP MFA：未完成 MFA 时管理入口一律返回 403 `mfa_required`，且平台管理员无法关闭自己的 MFA（409 `mfa_required_for_platform_admin`）。

管理 API（均需平台管理员身份 + MFA）：

- `GET /admin/tenants?query=&status=&limit=&offset=`：按名称或 slug 检索租户，返回 `{tenants, total}`，含成员数与租户状态（`active` / `suspended`）。成员数等跨租户读取通过 `app.platform_admin` GUC 在 RLS 策略中显式放行。
- `GET /admin/tenants/{id}`：租户详情（状态、MFA 策略、成员数、创建时间）。
- `POST /admin/tenants/{id}/status`：暂停或恢复租户。该敏感写操作会写入 `platform_audit_events` 审计表（操作者、动作、目标、结果、时间；目标不存在时也记录失败结果）。审计表为只增不改：应用角色仅有 SELECT/INSERT 权限，操作者账号删除后事件保留（actor_id 置空）。
- `GET /admin/audit-events`：查看最近的平台操作审计记录。

前端管理入口位于 `/admin`（平台管理员登录后默认落点），导航栏仅对平台管理员显示"平台管理"入口；未启用 MFA 时会被引导至 `/settings/security` 完成设置。

相关环境变量（`RN_` 前缀，见 `backend/.env.example` 与根目录 `.env.example`）：

- `RN_SESSION_TTL_SECONDS`：会话有效期，默认 1209600（14 天），同时作为 Cookie 的 Max-Age。
- `RN_SESSION_RENEWAL_WINDOW_SECONDS`：滑动续期窗口，默认 86400（1 天）。
- `RN_SESSION_COOKIE_SECURE`：会话 Cookie 是否带 Secure 标记，默认 false，生产环境应设为 true。
- `RN_INVITATION_TTL_SECONDS`：邀请有效期，默认 604800（7 天）。
- `RN_MFA_CHALLENGE_TTL_SECONDS`：MFA 挑战有效期，默认 300（5 分钟）。
- `RN_PLATFORM_ADMIN_EMAILS`：逗号分隔的平台管理员邮箱名单，默认空。名单内邮箱在注册/登录时获得平台管理员身份，移出名单后下一次认证时回收。
- `RN_APP_BASE_URL`：邀请邮件中链接使用的前端地址，默认 http://localhost:3000。
- `RN_SMTP_HOST` / `RN_SMTP_PORT` / `RN_SMTP_USERNAME` / `RN_SMTP_PASSWORD` / `RN_SMTP_FROM` / `RN_SMTP_USE_TLS`：邀请邮件的 SMTP 配置；未设置 host 时仅在 worker 日志中记录邀请链接。

## 计费与用量

新租户在注册事务内同时获得试用订阅：试用套餐（`trial`，14 天）的权益快照固定在订阅指向的不可变套餐版本上，之后发布新套餐版本不影响既有订阅。用量通过只增的 `usage_ledger_entries` 台账记账（reserve / confirm / release；应用角色仅有 SELECT/INSERT 权限，更新与删除由数据库权限拒绝），幂等键保证重试不重复计数，同一幂等键携带不同参数（metric 或 amount）会被拒绝。

- `GET /billing/summary`：返回当前订阅的套餐与用量余额。需要会话 Cookie 和 `billing:read` 权限（注册租户的所有者默认持有全部系统权限）；无当前订阅返回 404 `subscription_not_found`。响应形如 `{plan: {code, name, version}, status, trial_ends_at, current_period_start, current_period_end, metrics: [{metric, limit, used, reserved, remaining}, ...]}`，`metrics` 固定按 owners、companies、active_jobs、searches、matches、reports 顺序返回。
- 过期预订由 Celery 任务 `relationship_network.release_expired_usage_reservations` 清扫：任务在平台管理员 GUC 下跨租户写入 release 记录，数据库/网络失败自动指数退避重试，并发清扫器通过保存点跳过彼此已处理的预订。beat 调度每 5 分钟（300 秒）触发一次；beat 进程独立于 worker，本地可复用 worker 镜像运行：

```powershell
docker compose exec worker poetry run celery -A relationship_network_api.tasks:celery_app beat --loglevel=INFO
```

开发时也可以用 `celery -A relationship_network_api.tasks:celery_app worker -B` 让 worker 内嵌 beat。

## 线下订单与订阅生命周期

暂无商户号期间采用人工收款开通：租户提交线下订单（金额、付款凭证号、备注），平台管理员审核确认后激活按月订阅。订单携带 `payment_channel` 字段（当前固定 `offline`），为后续在线支付通道预留；发票申请首期不实现。

- `POST /billing/orders`：提交线下订单，需要 `billing:manage` 权限，返回 201。`(tenant_id, idempotency_key)` 唯一约束保证重复提交（含表单重试、双击）解析为同一张订单；同一幂等键携带不同参数返回 409 `idempotency_key_mismatch`。套餐不存在返回 404 `plan_not_found`。
- `GET /billing/orders`：本租户订单列表（需 `billing:read`），RLS 保证跨租户不可见。
- `POST /billing/subscription/cancel`：取消订阅（需 `billing:manage`），在当前有效期结束后才进入只读，重复调用幂等；无当前订阅返回 404 `subscription_not_found`。
- `GET /admin/orders?status=&tenant_id=`、`POST /admin/orders/{id}/confirm`、`POST /admin/orders/{id}/reject`：平台管理员审核入口（需平台管理员 + MFA）。确认/拒绝均幂等（重复操作返回当前状态、不重复写审计），对已拒绝订单确认返回 409 `order_already_rejected`，对已确认订单拒绝返回 409 `order_already_confirmed`。审核动作写入 `platform_audit_events`（`billing.order_confirm` / `billing.order_reject`）。

确认订单时，当前订阅（试用或在期付费）被替换为一个月期的 `active` 订阅；在期付费订阅续约时新周期顺延期末起算，不截断已购时长。Celery 任务 `relationship_network.expire_due_subscriptions` 每日把越过 `current_period_end` 的订阅置为 `expired`。到期租户的业务数据永久保留且可查看，写操作由 `deps.require_writable_tenant` 门禁拒绝（403 `subscription_read_only`，供后续业务写端点挂载）；重新提交订单并被确认后恢复写能力，用量账本保持不变。

前端入口：`/usage`（订阅状态、取消、订单申请与历史、只读横幅）与 `/admin/orders`（审核列表与操作）。

## 质量检查

```powershell
Push-Location backend
poetry run ruff check .
poetry run ruff format --check .
poetry run basedpyright
poetry run pytest -m "not integration"
Pop-Location

Push-Location frontend
bun run lint
bun run typecheck
bun run test
bun run build
Pop-Location
```

浏览器端到端测试使用独立 Bun 工具包，并在真实 Chrome 和 Edge 中保存页面验收截图；运行前需保证完整 Compose 环境已启动：

```powershell
Push-Location frontend/e2e
bun ci
bunx playwright install chrome msedge
bun run test:healthy
Pop-Location
```

真实依赖集成测试需先启动 PostgreSQL、Redis 和 MinIO，并设置与其一致的 `RN_*` 环境变量：

```powershell
Push-Location backend
poetry run pytest tests/integration/test_runtime_dependencies.py
Pop-Location
```

前端工程已经初始化 Tailwind CSS v4 与 shadcn/ui 配置，后续组件应复用 `components.json` 中的别名和主题约定。

CI 在主分支推送和所有拉取请求中执行后端格式、类型、测试和迁移往返，前端格式、类型、测试和生产构建，并从 Compose 全栈启动真实依赖、Celery 冒烟链路及 Chrome/Edge 页面流程。
