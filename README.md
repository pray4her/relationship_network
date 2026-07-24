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

- `POST /auth/register`：创建用户、租户和 owner 成员关系（单事务），返回 201 及 `{user, tenant, role}`，并种下会话 Cookie。邮箱重复返回 409 `email_already_registered`。未提供 `tenant_name` 时默认使用 `"{display_name} 的租户"`。
- `POST /auth/login`：返回与注册相同的 JSON 结构并种下 Cookie。邮箱不存在与密码错误统一返回 401 `invalid_credentials`，不区分原因。
- `POST /auth/logout`：删除服务端会话并以 `Max-Age=0` 清除 Cookie，无会话时也返回 204。
- `GET /auth/me`：返回当前身份；未认证返回 401 `not_authenticated`。剩余有效期进入续期窗口时自动滑动续期并重写 Cookie。
- `GET /tenants/current`：返回当前租户 `{id, name, slug, role}`；无有效成员关系返回 403。

成员关系可由两条路径写入：注册流程（只创建租户所有者），以及邀请流程——注册时传入 `invite_token`，或已登录后调用 `POST /invitations/accept` 加入租户（同一用户同时只能持有一个活跃成员关系，冲突返回 409 `already_in_tenant`）。成员的停用、启用、移除由 `POST /members/{id}/deactivate`、`POST /members/{id}/activate`、`DELETE /members/{id}` 提供，停用、降级、移除等变更必须经过 `membership_service`：该模块拒绝任何针对租户所有者的此类操作（并有对应单元测试），启用前还会校验用户在其他租户没有活跃成员关系。邀请接口需要 `members:invite` 权限，租户设置（如 MFA 策略）需要 `tenant:manage` 权限。

MFA 基于 TOTP：`POST /auth/mfa/setup` 生成密钥，`POST /auth/mfa/enable` 校验并启用（同时下发一次性恢复码），登录后由 `POST /auth/mfa/verify` 完成二次校验。租户开启 `mfa_required` 后，`get_tenant_context` 会拒绝未完成 MFA 的成员，返回 403 `mfa_required`。

相关环境变量（`RN_` 前缀，见 `backend/.env.example` 与根目录 `.env.example`）：

- `RN_SESSION_TTL_SECONDS`：会话有效期，默认 1209600（14 天），同时作为 Cookie 的 Max-Age。
- `RN_SESSION_RENEWAL_WINDOW_SECONDS`：滑动续期窗口，默认 86400（1 天）。
- `RN_SESSION_COOKIE_SECURE`：会话 Cookie 是否带 Secure 标记，默认 false，生产环境应设为 true。
- `RN_INVITATION_TTL_SECONDS`：邀请有效期，默认 604800（7 天）。
- `RN_MFA_CHALLENGE_TTL_SECONDS`：MFA 挑战有效期，默认 300（5 分钟）。
- `RN_APP_BASE_URL`：邀请邮件中链接使用的前端地址，默认 http://localhost:3000。
- `RN_SMTP_HOST` / `RN_SMTP_PORT` / `RN_SMTP_USERNAME` / `RN_SMTP_PASSWORD` / `RN_SMTP_FROM` / `RN_SMTP_USE_TLS`：邀请邮件的 SMTP 配置；未设置 host 时仅在 worker 日志中记录邀请链接。

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
