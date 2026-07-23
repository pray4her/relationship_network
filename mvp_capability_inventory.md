# CombineDatabase ↔ 全球人才平台 MVP：已完成能力盘点

> **文档目的（给 AI / 后续开发者）**  
> 本文把「三份设计文档描述的全球人才平台 MVP」与「本仓库 CombineDatabase 已落地代码」做一一对照。  
> 读完后应能回答：哪些阶段可直接复用、哪些需适配、哪些完全未做、技术栈差异是什么。  
>  
> **重要前提**：三份设计文档（`deployment_plan.md` / `relationship_network.md` / `system_dev_plan.md`）是方案；本仓库是**已实现的数据底座 + 检索 MVP**。二者不是同一代码库，能力可替换但不等于接口/表结构已对齐。

---

## 0. 一句话结论

| 层次 | 设计文档目标 | 本仓库现状 |
|------|-------------|-----------|
| 离线数据底座 | 论文+专家 → 统一人才 → 向量 → 搜索 | **已基本落地**（技术栈不同：OpenSearch 替代 PG+pgvector） |
| 合著关系网络 | 一跳/二跳合作图 | **未做** |
| 商业产品层 | 注册、JD匹配、报告、支付 | **未做**（仅有内部检索前端） |

**可直接替换进 MVP 的核心资产**：

1. 双源 ETL 流水线（scholars 专家名录 + frontiers 论文）
2. 规范人物 / 论文 / 关系 / 证据 claims 的统一 schema
3. 学者↔论文作者聚类匹配（canonical person）
4. 论文级 1024 维向量 + OpenSearch knn
5. 结构化检索 API + 自然语言找专家（LLM 解析 + knn + rerank）
6. 托管式内部验证前端（非 Streamlit，而是 Vue CDN）

---

## 1. 技术栈对照（AI 必须先读）

设计文档默认栈 vs 本仓库实际栈：

| 能力 | 设计文档（relationship_network） | CombineDatabase（本仓库） | 替换说明 |
|------|----------------------------------|---------------------------|----------|
| 主存储 | PostgreSQL 表 | OpenSearch 7 个索引 | 查询改写为 OpenSearch DSL，不是 SQL |
| 向量 | pgvector + BGE-M3 | OpenSearch `knn_vector` + DashScope `qwen3.7-text-embedding`（1024维） | 语义检索路径可替换；模型不同，需注意向量不可混用 |
| 任务编排 | 脚本/手工 | SQLite `manifest.db`（`file_manifest` + `ingest_jobs`） | 仅编排，不存业务数据 |
| 中间态 | SQL raw/authors 表 | Parquet / JSONL / bulk NDJSON（`data_pipeline/`） | 可重跑、可断点 |
| API | FastAPI `/search` | FastAPI（`search_app/`，默认 `:8010`） | 能力对等，路径不同 |
| NL 解析 | LLM → 结构化+语义 | `POST /api/search/nl-experts` + `prompts/nl_expert_search/` | **已实现** P7 等价物 |
| 内部前端 | Streamlit | `search_app/static/`（Vue3 + Element Plus CDN） | **已实现** P8 等价物 |
| 合著图 | PG 边表 / 可选 Neo4j | 无 | 需新建 |
| 认证/计费/报告 | 商业层 | 无 | 需新建 |

**数据源口径差异（重要）**：

- 设计文档：约 2000万论文 + 1800万专家名录（全量设想）。
- 本仓库：面向 **scholars（专家 Excel/CSV）+ frontiers（论文 Excel/CSV）** 的组级入库；规模取决于实际投放文件，不是固定「3800万」。
- 专家不是单独「experts 表」长期存在，而是经 silver/match 进入 `person`；论文进入 `publication`；人-文关系进入 `person_publication`。

---

## 2. 离线流水线对照（P0–P9）

本仓库阶段顺序（权威）：

```text
scan → bronze → silver → vector → match → index
```

入口脚本：`run_pipeline.py`（编排）、`scan_and_queue.py`（清单与任务）。

### P0 运行环境 — 部分完成 / 可替换

| 设计项 | 本仓库 | 状态 |
|--------|--------|------|
| Windows + Docker + Python | `docker-compose-opensearch.yml`、Python 3.12+、PowerShell 脚本 | ✅ 可用 |
| GPU 本地 BGE | 使用 **云端 DashScope embedding API**，不依赖本地 GPU | 🔁 路径不同但可替换 |
| Linux 全量生产机 | 文档有新机指南；生产边界未强制 | ⚠️ 需按部署方案补齐 |

关键文件：`docker-compose-opensearch.yml`、`.env.opensearch.example`、`docs/windows_new_host_fresh_run_guide.md`、`AGENTS.md`

### P1 抽样与画像 — 部分完成 / 弱等价

| 设计项 | 本仓库 | 状态 |
|--------|--------|------|
| DuckDB 百万级抽样脚本 | 无独立 `sample.py` | ❌ |
| 字段缺失率画像 JSON | silver 产出 `quality_report.json` 等质量统计 | 🔁 弱等价（面向已导入批次，非全库抽样） |
| 夹具冒烟 | `_scan_test/`、`_pipeline_test/` | ✅ 开发验证用 |

### P2 Raw 入库 — 已完成（形态不同）

| 设计项 | 本仓库等价物 | 状态 |
|--------|-------------|------|
| `raw_paper_sample` / `raw_expert_sample` | bronze：`scholars.rows.*` / `frontiers.rows.*`（JSONL/Parquet） | ✅ |
| PostgreSQL raw 表 | 文件系统中间态，非 SQL | 🔁 |
| `persons` / `person_sources` | silver/match 后的 `person` + 多类 `*_claim` 证据实体 | ✅ 更细（claims 可追溯） |

关键文件：`excel_to_json_batch.py`、`etl_transform_schema_v1.py`、`schema_v1.yaml`

### P3 论文→作者聚合 — 已完成（拆在 silver + match）

| 设计项 | 本仓库 | 状态 |
|--------|--------|------|
| 从论文拆作者 | silver 写 `author_occurrence`、identifier/affiliation/email claims | ✅ |
| ORCID / 姓名消歧 | silver 有 ORCID 相关合并；match 阶段 Union-Find 聚类 | ✅ |
| aliases、学术指标 | `name_aliases`、`h_index`、`total_citations` 等 person 字段 | ✅ |
| `research_summary` 文本画像 | **未单独字段**；语义靠论文 Title/Abstract/Keywords 向量 | 🔁 路径不同 |
| 独立 `authors` 中间表 | 由 `person` + claims + `person_publication` 替代 | 🔁 |

关键文件：`etl_transform_schema_v1.py`、`match_person_clusters_v1.py`

### P3.5 合著关系网络 — 未做

| 设计项 | 本仓库 | 状态 |
|--------|--------|------|
| `paper_authors` / `coauthor_edges` | 无边表、无图索引、无图 API | ❌ |
| 一跳/二跳/国内合作者 | 无 | ❌ |
| Neo4j | 无 | ❌ |

**可复用的前置数据**：已有 `person_publication`（人-文关系），可据此离线生成合著边，不必重做作者聚合。

### P4 论文作者 ↔ 专家名录合并 — 已完成

| 设计项 | 本仓库 | 状态 |
|--------|--------|------|
| 双库实体对齐 | `match_person_clusters_v1.py`：scholars ↔ frontiers 聚类 | ✅ |
| Splink 概率匹配 | 自研规则 + Union-Find + 强名阈值等（非 Splink） | 🔁 算法不同，目标相同 |
| `canonical_person_id` | 有 | ✅ |
| 人工复核队列 | 无独立产品模块 | ❌ |
| 字段冲突消解 | match/silver 内合并逻辑 + 排名/华人身份等规则 | ✅ 部分 |

附加 enrichment（设计文档未强调、本仓库已有）：

- `chinese_identity`：`国内华人` / `海外华人` / `外国人`
- `qs_top200_rank`、`world_top500_rank`（`reference_data/` + `institution_rankings.py`）

### P5 Embedding — 已完成（对象不同）

| 设计项 | 本仓库 | 状态 |
|--------|--------|------|
| 对人 `research_summary` 向量化 | 对 **publication**（Title+Abstract+Keywords）向量化 | 🔁 |
| BGE-M3 本地 | DashScope `qwen3.7-text-embedding`，1024 维 | 🔁 |
| 断点续跑 | SQLite embedding checkpoint | ✅ |
| 回写 | `data_pipeline/vector/<run_id>/` → index 入 `publication_v1.embedding` | ✅ |

**检索语义后果**：专家相关性 = 其关联论文向量的召回/精排再 **Max 聚合到人**，不是「人向量直接近邻」。这与设计文档「persons.embedding」不同，但对「按研究方向找专家」目标可替换。

关键文件：`vector_embed_publications_v1.py`

### P6 向量索引 + 搜索 API — 已完成

| 设计项 | 本仓库 | 状态 |
|--------|--------|------|
| HNSW / knn | OpenSearch knn（faiss/HNSW 映射见 `opensearch_mapping_v1.json`） | ✅ |
| 结构化检索 | `POST /api/search/query`、`/count` | ✅ |
| 融合排序 | NL 路径：knn → rerank → Max 聚合 | ✅（NL）；通用 `/query` 以结构化为主 |
| 7 实体目录与字段元数据 | `GET /api/search/entities` 等 | ✅（超出设计最小集） |
| 异步导出 CSV/XLSX | `/api/search/export*` | ✅（设计未强调） |

关键文件：`search_app/main.py`、`query_builder.py`、`opensearch_client.py`、`create_indices.ps1`、`bulk_import.ps1`

### P7 自然语言查询解析 — 已完成（MVP 级）

| 设计项 | 本仓库 | 状态 |
|--------|--------|------|
| LLM → 结构条件 + 语义条件 | `person_query_tree` + `vector_query` | ✅ |
| JSON Schema | `prompts/nl_expert_search/output_schema.json` | ✅ |
| 意图路由到关系图 | **无**（无合著查询意图） | ❌ |
| LLM 失败降级 | 需读实现确认；提示词侧有约束 | ⚠️ |
| 字段白名单 | qs/fortune/华人/国家/机构/h_index/被引 | ✅ |

提示词：`prompts/nl_expert_search/{system.md,few_shots.md,output_schema.json}`  
实现：`search_app/nl_expert_search.py`、`dashscope_clients.py`、`prompt_loader.py`  
接口：`POST /api/search/nl-experts`

### P8 内部 MVP 前端 — 已完成（非 Streamlit）

| 设计项 | 本仓库 | 状态 |
|--------|--------|------|
| 自然语言输入 → 看结果 | Tab「自然语言找专家」 | ✅ |
| 结构化筛选调试 | Tab「结构化检索」+ DSL 预览 | ✅ |
| 正式 React 商业前端 | 无 | ❌（属商业层） |

文件：`search_app/static/{index.html,app.js,styles.css}`，入口 `python run_search_api.py`

### P9 验收 / 全量 — 部分完成

| 设计项 | 本仓库 | 状态 |
|--------|--------|------|
| 单元测试 | `tests/`（NL 解析、聚合、query builder、华人身份、机构排名、embedding 文本等） | ✅ |
| 夹具端到端 | `_scan_test/`、`_pipeline_test/`、样例产物 `data_pipeline_combonedata_test/` | ✅ |
| 向量评测样本 | `vector_eval_samples/`（本地） | ✅ |
| 设计文档中的 6 类验收查询（含合著/二跳） | 合著类不可测；其余结构/语义/混合可测 | ⚠️ |
| 全量 Linux 生产跑批 | 流程具备，需按环境与数据规模执行 | ⚠️ |

---

## 3. 商业产品层对照（system_dev_plan）

下列模块在本仓库中 **均未实现**（不要误判为「检索前端已有」=「产品已有」）：

| 模块 | 状态 |
|------|------|
| 注册登录 / JWT / 多租户 / RBAC | ❌ |
| 企业资料 / 职位 / JD 上传与解析 | ❌ |
| `/match` 批量匹配与人才池 | ❌ |
| 人才详情页产品化（收藏、标签、负责人、解锁联系方式） | ❌ |
| 深度匹配报告 RAG + PDF | ❌ |
| 订阅/支付/用量/webhook | ❌ |
| 通知、预警、反馈闭环 | ❌ |
| 开放企业 API / 合规执行模块 | ❌ |
| 生产 Nginx + HTTPS + 对象存储 | ❌（仅有本地 OpenSearch Compose） |

**可复用底座**：商业层的「搜索 / NL 找专家 / 结构化过滤」应直接调用本仓库 `search_app` 能力，而不是按设计文档从零再写 pgvector 检索。

---

## 4. 逻辑数据模型（本仓库权威）

定义源：`schema_v1.yaml` ↔ OpenSearch：`opensearch_mapping_v1.json`

| 实体 / 索引 | 职责 | 对应设计文档概念 |
|-------------|------|------------------|
| `person` / `person_v1` | 规范人才主档 | `persons` |
| `publication` / `publication_v1` | 论文（含 `embedding`） | papers + 向量载体 |
| `person_publication` / `person_publication_v1` | 人-文关系 | paper_authors（仅人-文，无边） |
| `author_occurrence` | 篇级作者出现（去重前） | 聚合过程证据 |
| `author_identifier_claim` | ORCID / ResearcherID 证据 | person_sources 子集 |
| `author_affiliation_claim` | 机构/国家证据（含排名） | person_sources 子集 |
| `author_email_claim` | 邮箱证据（含 Fortune 域名） | person_sources 子集 |

编排库（非业务）：SQLite `manifest.db` → `file_manifest`、`ingest_jobs`。

---

## 5. 在线 API 能力清单（已实现）

服务入口：`run_search_api.py` → `search_app.main:app`

| 方法 | 路径 | 能力 | MVP 映射 |
|------|------|------|----------|
| GET | `/` | 托管前端 | P8 |
| GET | `/api/search/entities` | 实体目录 | P6 |
| GET | `/api/search/entities/{key}/fields` | 字段元数据 | P6 |
| POST | `/api/search/query` | 结构化检索 | P6 结构化路 |
| POST | `/api/search/count` | 计数 | P6 |
| POST | `/api/search/export` | 异步导出 | 增强 |
| GET | `/api/search/export/jobs/{id}` | 导出状态 | 增强 |
| GET | `/api/search/export/jobs/{id}/download` | 下载 | 增强 |
| POST | `/api/search/nl-experts` | NL 找专家 | P6+P7 |

**不存在的端点（设计有、本仓无）**：`/match`、关系图查询、报告生成、认证、支付。

---

## 6. 关键脚本与职责地图（给 AI 改代码时用）

```text
scan_and_queue.py          # 扫描源文件 → manifest + jobs
excel_to_json_batch.py     # bronze：Excel/CSV → 组级 rows
etl_transform_schema_v1.py # silver：统一 schema、claims、质量报告、bulk
vector_embed_publications_v1.py  # vector：论文 embedding + checkpoint
match_person_clusters_v1.py      # match：双源人物聚类 → canonical person
institution_rankings.py    # QS200 / Fortune500  enrichment
run_pipeline.py            # 编排六阶段；index 调 PS1
create_indices.ps1         # 建 OpenSearch 索引
bulk_import.ps1            # bulk NDJSON 导入
pipeline_storage.py        # Parquet/JSONL/bulk IO
run_search_api.py          # 启动检索服务
search_app/*               # FastAPI + NL + 前端
prompts/nl_expert_search/* # NL 提示词
reference_data/*           # 排名参考 JSON
tests/*                    # unittest
```

流水线产物约定目录：`data_pipeline/{bronze,silver,vector,match,index}/<run_id>/`（或本地测试目录变体）。

---

## 7. 替换决策建议（给项目规划用）

### 建议直接采用本仓库，不再按设计文档重做的部分

1. **双源 ETL + 统一 person/publication schema**（替代 P2–P4 的 PG 方案）
2. **论文向量 + knn + rerank + 聚合到专家**（替代 P5–P6 的 persons.embedding + pgvector）
3. **NL 意图解析 + 内部验证前端**（替代 P7–P8 的示意实现）
4. **华人身份 / QS / Fortune  enrichment**（设计文档未写清，已是差异化资产）

### 建议在本仓库上增量新建的部分

1. **合著边构建**（从 `person_publication` 生成 edges；MVP 用 OpenSearch 或 PG/边表均可）
2. **NL 意图扩展**：`related_to` / `coauthor` 路由
3. **商业产品层**（认证、JD 匹配、报告、计费）— 独立服务，检索调用本 API
4. **生产部署拆分**：批处理节点 vs 在线 API 节点

### 不建议做的事

1. 为对齐文档而把已跑通的 OpenSearch 栈整体迁回 PostgreSQL+pgvector（除非有强运维约束）
2. 把旧文档中的 `core/` JournalCleaner 路径当作现行架构（本仓库已无该目录；`docs/core_data_matching_flow.md` 等属历史残留）

---

## 8. AI 工作协议（修改本仓库时）

1. **以代码与 `schema_v1.yaml` / `opensearch_mapping_v1.json` 为准**；设计文档与部分 `docs/*` 可能过时。
2. 改 schema 必须 **yaml + mapping 同步**。
3. 流水线阶段名固定为 `scan,bronze,silver,vector,match,index`；漏写 `vector` 的文档视为过时。
4. 专家语义检索优先走 **论文向量聚合**，不要假设存在 `person.embedding`。
5. 密钥只放 `.env`；模板是 `.env.opensearch.example`。
6. 验证优先：`tests/` unittest + `_pipeline_test/` 冒烟；大文件与 `manifest.db` 默认不入库。

---

## 9. 状态总表（快速扫描）

图例：✅ 已完成可替换｜🔁 目标等价但实现不同｜⚠️ 部分｜❌ 未做

| MVP 阶段 / 模块 | 状态 |
|-----------------|------|
| P0 环境 | ⚠️ / 🔁 |
| P1 抽样画像 | ⚠️ |
| P2 Raw 入库 | ✅ / 🔁 |
| P3 作者聚合 | ✅ / 🔁 |
| P3.5 合著网络 | ❌ |
| P4 双库合并 | ✅ / 🔁 |
| P5 Embedding | ✅ / 🔁（论文级） |
| P6 搜索 API | ✅ |
| P7 NL 解析 | ✅（无关系意图） |
| P8 内部前端 | ✅ / 🔁（Vue） |
| P9 验收全量 | ⚠️ |
| 认证租户 | ❌ |
| 企业/JD/匹配 | ❌ |
| 人才池/详情产品化 | ❌ |
| 深度报告 | ❌ |
| 支付用量 | ❌ |
| 通知预警反馈 | ❌ |
| 开放 API / 合规执行 | ❌ |

---

## 10. 最终概括（给 AI 的记忆句）

> CombineDatabase 已经实现「学者名录 + 论文 → 规范人物与证据 → 论文向量 → OpenSearch 结构化检索 + 自然语言找专家」这条数据与检索主链，可替代全球人才平台 MVP 中的离线底座与内部搜索验证（P2–P8 主体）。  
> 尚未实现合著关系网络与全部商业产品层。  
> 后续工作应 **站在 OpenSearch + 现有 schema/API 上扩展**，而不是从三份设计文档的 PostgreSQL 示意代码重新开工。
