# 01 — 接通检索底座：服务认证、契约版本、健康检查与假服务

**Parent:** GitHub Issue [#12](https://github.com/pray4her/relationship_network/issues/12) — `[MVP-11] 建立检索底座版本化内部服务契约`

**What to build:** 本产品 API 与 Worker 能以服务身份、携带检索契约版本和请求标识调用假检索底座的健康检查；认证失败与契约版本不兼容立即失败且不重试；超时、网络错误、429 和 5xx 作为安全读取重试并有上限。Compose 可独立跑起假检索底座。平台健康状态不把检索底座算进去。没有租户界面，也不扣额度。

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

## Acceptance criteria

- [ ] 检索底座基址、服务密钥、超时和检索契约版本只通过 `RN_` 配置注入；密钥不以明文入库或提交。
- [ ] 检索契约版本 v1 声明可执行职位需求 Schema v1 与 v2（二者可执行条件目录相同）；请求携带该版本，成功响应回显请求标识。
- [ ] 只有正确的服务凭据能通过假检索底座认证；缺失或错误凭据得到稳定的 `unauthenticated` 或 `forbidden`，且 `retryable=false`。
- [ ] 契约版本不兼容得到 `contract_version_incompatible`，不重试。
- [ ] 适配器对健康检查执行最多 3 次尝试：超时、网络错误、429、5xx 可重试并退避，尊重 `Retry-After`；httpx 传输层重试保持为 0。
- [ ] 假检索底座可独立运行，提供健康检查与认证/版本不兼容/超时/5xx 场景开关，测试间可重置，不依赖真实检索集群。
- [ ] 契约测试打真实适配器而非裸 HTTP；假服务与适配器共用同一套契约模型。
- [ ] 单元测试可在无 Docker 时对假服务进程内完成；Compose 提供假检索底座服务及容器健康检查，API 与 Worker 指向该服务。
- [ ] `/health/ready` 的依赖仍仅为 PostgreSQL、Redis 与对象存储；检索底座不可用不得改变平台健康状态语义。
- [ ] 本切片不新增租户或平台管理 HTTP 路由、不写 OpenSearch DSL、不产生用量台账、不记录服务密钥。
