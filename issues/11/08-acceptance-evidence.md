# 08 — Compose 全链路与浏览器验收证据

**Parent:** GitHub Issue [#11](https://github.com/pray4her/relationship_network/issues/11) — `[MVP-10] 接入 OpenRouter 并完成职位需求解析确认`

**Spec:** [08-compose-and-browser-acceptance.md](08-compose-and-browser-acceptance.md)

本文件记录 08 的可独立判断证据。父 Issue **不在此关闭**；08 是关闭门禁，需人工确认后再关。

## 产品边界

Compose 与 CI 默认走仓内假 OpenRouter，不调用 `https://openrouter.ai/api/v1`，不要求真实 API 密钥，不产生外部模型费用。线上最小探测仍可改回真实 URL/密钥，**不是**回归门禁。

```text
已认证 UI/API → PostgreSQL 快照/任务/Outbox → 测试直接调用 worker 入口
  → 假 OpenRouter → 恰好一份可编辑草稿或稳定失败 → SSE / 职位详情页
```

集成测试不断言 Celery 私有实现：CI compose job 在跑 `tests/integration/` 期间停止 `worker`、`outbox-dispatcher`、`platform-scheduler`、`llm-maintenance-worker`，测完再启动并做 Celery smoke。

## 假 OpenRouter

模块：`backend/src/relationship_network_api/fake_openrouter.py`

- 默认按 `response_format.json_schema.name` 分支：`relationship_network_config_probe` → `{"capability":"ok"}`；`relationship_network_job_requirement` → Schema v2 JSON，证据 quote 从请求 `sources` 正文切片。
- 未覆盖模型（含种子 `x-ai/grok-4.5` 与 `test/success`）按 schema 成功。
- 模型场景：`test/invalid-structure`、`test/rate-limited`（429 + `Retry-After`）、`test/server-error`、`test/timeout`、`test/disconnect`、`test/late-response`、`test/provider-denied`、`test/delayed-success`、`test/delayed-generation`、`test/with-conflicts`。
- 仍校验 `stream: false`、禁止 `models`、ZDR / `data_collection=deny` / `require_parameters`、`json_schema.strict`。

Compose 服务 `fake-openrouter`：`127.0.0.1:18080`；`api`/`worker` 默认 `RN_OPENROUTER_BASE_URL=http://fake-openrouter:8080/api/v1`，worker dummy key `fake-openrouter-key`。`.env.example` / `backend/.env.example` 同步 dummy URL/key，以及 e2e 平台管理员邮箱 `llm-e2e-admin-chrome@example.com,llm-e2e-admin-edge@example.com`。

## 质量门禁（本机实际命令）

工作目录均为仓库根，除非另注。

### 后端四项

```text
cd backend
poetry run ruff check .          # All checks passed
poetry run ruff format --check . # 160 files already formatted
poetry run basedpyright          # 0 errors, 0 warnings, 0 notes
poetry run pytest -m "not integration"
# 481 passed, 88 deselected in 17.37s
```

CI backend job 在 alembic `upgrade → downgrade → upgrade` 之后跑：

```text
poetry run pytest tests/integration/test_migration_roundtrip_invariants.py
```

断言种子配置（v1 时为 `x-ai/grok-4.5`）、`legacy_requirement_exempt`、RLS、不可变表仅 SELECT/INSERT、调度/dispatcher/维护固定函数 EXECUTE、部分唯一索引。测试内不再 downgrade。

### 前端四项

```text
cd frontend
bun run lint      # biome check .  206 files, no fixes
bun run typecheck # tsc --noEmit
bun run test      # Test Files 31 passed; Tests 196 passed
bun run build     # Next.js 16.2.9 生产构建成功
```

### Compose 集成与浏览器

```text
# 08 相关集成（真实 PostgreSQL；pipeline fixture 指向 in-process 假 OpenRouter）
cd backend
poetry run pytest tests/integration/test_requirement_parsing_pipeline.py \
  tests/integration/test_requirement_task_races.py \
  tests/integration/test_llm_configuration_pipeline.py \
  tests/integration/test_migration_roundtrip_invariants.py \
  tests/integration/test_job_requirement_durability.py
# 17 passed in 28.85s
```

覆盖：认证 API 创建快照/任务 → 领取执行 → 假上游 → 一份可编辑草稿或稳定失败 → SSE/`Last-Event-ID`；重复投递、租约过期、取消/归档迟到、NOTIFY 丢失后补读、`late_response`；探测成功立即启用、失败、取消、`expected_current` 冲突。`pipeline` fixture 结束时把 `llm_configuration_current` 指回测试前版本，避免污染后续用例。

```text
cd frontend/e2e
bun run test:healthy
# 纳入 health-page、workspace-pages、llm-configuration、
# requirement-parsing、requirement-boundaries；projects = chrome + edge
# 边界矩阵仅 Chrome 全跑，Edge skip（见下方排除项）

# 降级态（停 MinIO 后 /health/ready 返回 503）
bun run test:degraded
# 2 passed (chrome + edge, 5.1s)；随后 start minio，ready 恢复 200
```

浏览器主路径：平台管理员查看配置、提交异步探测、等待启用、失败、取消、并发冲突、复制历史；租户来源分段 → 生成 → 草稿 → 确认 v1 → 启用后复制 → 确认 v2 → 取消进行中任务。成功路径 `testInfo.attach` 截图。API 夹具推进部分 Server Action 不稳定步骤，浏览器仍断言职位详情页可见结果。

CI compose artifact：`browser-verification` ← `frontend/e2e/test-results`（Playwright 失败截图/trace；成功路径附件在报告中）。

## 明确排除项

- **真实 OpenRouter 探测不是 CI 门禁。** 本地/线上改回真实 URL 与密钥后的最小探测是独立运行能力检查。
- **历史启用待确认（`legacy_requirement_exempt`）不能由应用创建。** 浏览器门禁以集成测试插入豁免 + 职位详情只读/Alert 为准；e2e 不伪造应用写路径。
- **边界矩阵 Edge skip。** `requirement-boundaries.spec.ts` 仅 Chrome 全量；Edge 以主路径（parsing / LLM 配置）截图为证，控制 CI 时间。
- **SSE `reconnecting` 不作为单独稳定断言。** 断线恢复以刷新后从 DB 恢复任务/草稿为等价证据。
- **产品 UI 不做视觉重做。** 沿 ADR 0024 / `docs/openai-DESIGN.md` / `globals.css` 语义 token；无新色彩、无暗色模式。
- **本机全量 `tests/integration/` 若在 Playwright 之后跑，可能被当前 LLM 配置污染。** CI 顺序是 integration 先于 e2e，且 runner 卷为新库（种子 `x-ai/grok-4.5`）。pipeline fixture 现已恢复 current 指针。

## 对照验收标准

| 标准 | 证据 |
|------|------|
| 可编程假上游场景表 | `fake_openrouter.py` + `tests/test_fake_openrouter.py` |
| CI/本地不碰真实上游 | `compose.yaml`、`.env.example`、CI `cp .env.example .env` |
| 最高缝 API→草稿/失败→SSE | `test_requirement_parsing_pipeline.py` |
| 平台管理员浏览器 | `llm-configuration.spec.ts` 进 `test:healthy` |
| 租户解析确认 v1/v2 | `requirement-parsing.spec.ts` |
| 边界矩阵 | `requirement-boundaries.spec.ts`（Chrome） |
| 竞态不重复草稿/错切版本 | `test_requirement_task_races.py` |
| 迁移语义 | backend alembic 往返 + `test_migration_roundtrip_invariants.py` |
| 后端/前端四项 | 见上方命令输出 |
| Compose 健康/降级 | `test:healthy` / `test:degraded`；Celery smoke 保留 |
