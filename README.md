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
