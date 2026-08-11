# 08 — 完成 Compose 全链路与浏览器验收

**Parent:** GitHub Issue [#11](https://github.com/pray4her/relationship_network/issues/11) — `[MVP-10] 接入 OpenRouter 并完成职位需求解析确认`

**What to build:** 在完整 Compose 产品边界中使用确定性的假 OpenRouter 验证平台配置和租户职位需求全链路，使 CI 不依赖真实 API 密钥或外部费用，并留下可以支持父 Issue 验收的迁移、自动化和真实浏览器证据。

**Blocked by:** 04 — 可靠执行并实时展示职位需求解析任务; 06 — 确认并修订不可变职位需求版本; 07 — 管理历史 Schema、保留策略与审计边界.

**Status:** ready-for-agent

## Acceptance criteria

- [ ] Compose 提供可由测试按场景控制的假 OpenRouter，支持严格有效响应、Schema 无效、429 与 `Retry-After`、5xx、超时、请求后断连、迟到响应、上游提供方选择和延迟生成元数据。
- [ ] CI 和本地自动化不调用真实 OpenRouter、不要求真实 API 密钥且不产生外部模型费用；线上配置的最小探测仍是独立运行能力检查，不是回归评估门禁。
- [ ] 最高测试缝完整覆盖：已认证 UI/API 请求 → PostgreSQL 输入快照、任务和 Outbox → Dispatcher/Celery → 假 OpenRouter → 有效草稿或稳定失败 → SSE → 职位详情页。
- [ ] 平台管理员浏览器流程覆盖查看配置、提交异步配置、SSE 进度、探测成功后立即启用、失败、并发冲突、取消及复制历史配置。
- [ ] 租户浏览器流程覆盖来源分段修正、解析成功、任务重试、断线恢复、取消、草稿编辑、来源冲突解决、确认 v1、启用中修订 v2 和手工复制版本。
- [ ] 浏览器验收覆盖归档优先及只读、历史启用职位待确认、无权限成员、只读租户、乐观并发冲突和稳定业务错误展示。
- [ ] 集成测试验证重复消息、租约过期、NOTIFY 丢失、未知结果、迟到响应及取消竞态不会产生重复调用提交、重复草稿或错误版本切换。
- [ ] 真实 PostgreSQL 验证 RLS 允许/拒绝、复合外键、部分唯一索引、任务状态转换、不可变表权限、平台 scope 和受限维护函数。
- [ ] 新增迁移在 PostgreSQL 上完成 upgrade → downgrade → upgrade，并验证初始配置、历史职位豁免、RLS、授权、索引和固定函数均可恢复。
- [ ] 后端 Ruff、格式检查、basedpyright、单元测试和真实依赖集成测试全部通过。
- [ ] 前端 Biome、TypeScript、Vitest 和生产构建全部通过。
- [ ] Compose 服务保持健康，Celery 冒烟、健康态与降级态验收不回归；新增真实 Chrome/Edge 流程保存必要截图或等价浏览器证据。
- [ ] 验收证据记录实际命令、通过结果和任何明确排除项，使父 Issue #11 可以在不依赖聊天记录的情况下判断完成度。
