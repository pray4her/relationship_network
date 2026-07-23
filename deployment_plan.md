# 自然语言人才检索平台 · 部署实施方案（公司电脑 + 逐步教学）

> 适用场景：2000万期刊论文库 + 1800万专家名录库 → 自然语言找人才
> 首期目标：抽 50–100万样本跑通整条流水线，确认检索效果后再上全量
> 部署形态：Windows 公司机（WSL2 + Ubuntu）做开发/样本验证；Linux 服务器做全量生产
> 角色分工：老板跟我确认架构与环境；实习生执行数据批处理与脚本开发；我负责写脚本、定流程、做验收

---

## 一、硬件现实与应对策略

| 项目 | 本机（Windows + 低显存显卡） | Linux 服务器（你提供） |
|------|------------------------------|------------------------|
| 用途 | 样本验证、前端、查询引擎 | 全量 Embedding、生产检索 |
| 显存 | 低（4–8GB） | 视配置（建议 ≥16GB） |
| 内存 | ≥16GB 可用 | ≥64GB 推荐 |
| 磁盘 | 样本 ~20GB | 全量向量 ~30–50GB |

**Embedding 模型显存对照（选模型时看这个）：**

| 模型 | 维度 | 显存占用 | 说明 |
|------|------|----------|------|
| bge-small-zh-v1.5 | 512 | 1–2GB | 最快最省，中文为主可用 |
| bge-large-zh-v1.5 | 1024 | 4–8GB | 中文效果好，低显存首选 |
| **BGE-M3** | 1024 | 6–10GB | **中英多语 + 100+语言**，论文库含英文必选 |

**结论：**
- 样本阶段（≤100万）：本机低显存显卡跑 BGE-M3，batch 调小（8–16）即可，约 1–3 小时。
- 全量阶段（2200万）：本机 CPU 要跑几天不现实 → **必须放到 Linux 服务器**（你提供）或临时云 GPU 跑完，再把向量导回。

**国内环境注意（提前记好）：**
- pip 用清华镜像：`pip install -i https://pypi.tuna.tsinghua.edu.cn/simple 包名`
- BGE-M3 模型从魔搭下载（HuggingFace 在国内常被墙）：
  `from modelscope import snapshot_download; snapshot_download('BAAI/bge-m3')`
- LLM 查询解析优先用 **Qwen-Max（阿里云百炼）** 或 **DeepSeek**，国内稳定便宜；GPT-4o 走你已有的代理。

---

## 二、阶段路线图

| 阶段 | 名称 | 主要产出 | 预计耗时 | 执行人 |
|------|------|----------|----------|--------|
| P0 | 环境与硬件检测 | WSL2+Ubuntu、Docker、GPU 可用确认 | 0.5天 | 老板+我 |
| P1 | 样本抽取与数据探查 | 100万论文样本 + 50万专家样本 + 字段画像 | 0.5天 | 实习生 |
| P2 | 统一 Schema 与导入 PG | raw 表 + 统一 persons 表结构 | 0.5天 | 实习生 |
| P3 | 论文库作者聚合 | authors 聚合表 + 研究画像 | 1天 | 实习生 |
| P4 | 双库实体对齐合并 | 统一 persons 表（含 match_confidence） | 1–2天 | 实习生 |
| P5 | Embedding 生成 | persons.embedding 向量列 | 本机1–3h/全量交服务器 | 实习生 |
| P6 | 向量索引 + 检索 API | FastAPI /search 接口 | 1天 | 实习生 |
| P7 | 自然语言查询引擎 | LLM 查询解析 + 混合检索融合 | 1天 | 老板+实习生 |
| P8 | 前端界面（MVP） | Streamlit 对话式检索页 | 0.5天 | 实习生 |
| P9 | 验收与交付 | 验收报告 + README + 交接 | 0.5天 | 老板+我 |

---

## 三、各阶段详细步骤

### P0 · 环境与硬件检测

**① 在 Windows 上检测硬件（管理员 PowerShell 或 Git Bash）：**
```powershell
nvidia-smi                                              # 看显卡型号 + 显存
wmic computersystem get TotalPhysicalMemory             # 看总内存(字节)
wmic diskdrive get Model,Size                           # 看磁盘剩余
```

**② 安装 WSL2 + Ubuntu 22.04（管理员 PowerShell）：**
```powershell
wsl --install -d Ubuntu-22.04
# 装完重启，首次进入设用户名/密码
wsl -d Ubuntu-22.04    # 进入 Ubuntu 终端
```

**③ 安装 Docker Desktop（Windows）**：勾选 "Use WSL 2 based engine"，并在 Settings → Resources → WSL Integration 里勾选 Ubuntu-22.04。

**④ 在 Ubuntu 内准备基础环境：**
```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip git curl
# 验证
docker run hello-world
nvidia-smi          # 若 Docker 要用 GPU，需在 Docker Desktop 勾选 GPU support 并装 NVIDIA Container Toolkit
```

**验收**：`nvidia-smi` 能看到显卡；`docker run hello-world` 成功；Ubuntu 内 python3.11 可用。

---

### P1 · 样本抽取与数据探查

把 CSV 放到 Windows 某目录（如 `D:\data\`），WSL 内通过 `/mnt/d/data/` 访问。

**① 用 DuckDB 快速抽样（不加载全量，几十 GB 的 CSV 也能秒抽）：**
```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple duckdb
```
```python
# sample.py
import duckdb
# 论文库抽 100万（按主键哈希随机抽，保证分布均匀）
duckdb.sql("""
COPY (SELECT * FROM read_csv_auto('D:/data/papers.csv')
      WHERE hash(rowid) % 20 = 0 LIMIT 1000000)
TO 'D:/data/papers_sample.csv' (HEADER, DELIMITER ',')
""")
# 专家库抽 50万
duckdb.sql("""
COPY (SELECT * FROM read_csv_auto('D:/data/experts.csv')
      WHERE hash(rowid) % 36 = 0 LIMIT 500000)
TO 'D:/data/experts_sample.csv' (HEADER, DELIMITER ',')
""")
```

**② 数据探查脚本（字段缺失率、覆盖率、重复率）→ 输出 profile.json：**
```python
import duckdb, json
for name, f in [("papers","D:/data/papers_sample.csv"),("experts","D:/data/experts_sample.csv")]:
    df = duckdb.sql(f"SELECT * FROM read_csv_auto('{f}')").df()
    prof = {c: {"null_rate": float(df[c].isna().mean()),
                "nunique": int(df[c].nunique())} for c in df.columns}
    json.dump(prof, open(f"{name}_profile.json","w"), ensure_ascii=False, indent=2)
print("字段画像已生成，用来定统一 schema 映射")
```

**验收**：两个样本 CSV 生成；profile.json 列出每个字段的缺失率——重点看 `email / name / institution / title / abstract` 的覆盖率，据此定映射表。

---

### P2 · 统一 Schema 与导入 PostgreSQL

**① Docker 起 PostgreSQL + pgvector：**
```bash
docker run -d --name pg -p 5432:5432 -e POSTGRES_PASSWORD=你的密码 ankane/pgvector:latest
```

**② 建表（统一 persons 表 + 来源关联表 + 两张 raw 样本表）：**
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE raw_paper_sample (LIKE 不适用，按 CSV 字段建列，或先全 TEXT 导入再清洗);
CREATE TABLE raw_expert_sample (...);
CREATE TABLE persons (
  person_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  canonical_name TEXT,
  aliases       TEXT[],
  institution   TEXT,
  department    TEXT,
  email         TEXT,
  phone         TEXT,
  title         TEXT,
  research_summary TEXT,        -- 综合研究画像文本
  research_fields   TEXT[],
  paper_count   INT,
  citation_count INT,
  h_index       INT,
  match_confidence FLOAT,
  sources       TEXT[],
  embedding     vector(1024),   -- BGE-M3 维度
  created_at    TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE person_sources (
  person_id UUID, source_type TEXT, source_id TEXT,
  raw_fields JSONB, matched_confidence FLOAT, matched_at TIMESTAMPTZ
);
```

**③ 导入脚本（用 COPY 高效灌入 raw 表）：**
```python
import psycopg2
conn = psycopg2.connect("dbname=postgres user=postgres password=你的密码 host=localhost")
cur = conn.cursor()
cur.copy_expert("COPY raw_paper_sample FROM 'D:/data/papers_sample.csv' WITH CSV HEADER", open(r'D:/data/papers_sample.csv'))
# experts 同理
conn.commit()
```

**验收**：两张 raw 表各 ~100万 / 50万行；pgvector 扩展已启用；persons 表结构就绪。

---

### P3 · 论文库作者聚合（样本）

**目标**：把论文级数据降维到作者级，生成研究画像。

```python
# aggregate_authors.py 核心逻辑
# 1. 按 (email) 或 (institution + name) 或 orcid 归并
# 2. 每人算 paper_count / citation_sum / h_index(近似) / research_fields(关键词) / research_summary(摘要拼接)
# 3. 写 authors 表
```

聚合规则（消歧）：
- 精确键：`email` 完全相同（且非 gmail/qq/163 等公共邮箱）
- 次精确：`institution + name`（清洗后）相同
- 写入 `aliases` 收集不同拼写

**验收**：authors 表行数明显少于论文样本（如 100万论文 → 约 20–40万作者）；每人有 research_summary 文本。

---

### P3.5 · 作者关系网络构建（新增）

> 合著关系网是本项目的关系型资产，支撑"经合作者推荐人才"与"找国内合作者落地"两大场景。详细设计见 `relationship_network.md`。
>
> **目标**：在 P3 聚合出的 authors 之上，构建合著边表 `coauthor_edges`（节点=人，边=合著，权重=合著论文数），样本阶段用 PostgreSQL 边表+递归 CTE 跑通两个场景；全量/深度分析引入 Neo4j。
>
> **验收**：① 能列出某教授合作过的国内教授；② 能经 2 跳合作网络推荐符合人才计划资格的人选。

### P4 · 双库实体对齐合并（样本）

**目标**：判断 authors（来自论文）与 raw_expert_sample（专家名录）是不是同一人，合并成统一 persons。

**用 Splink 做概率匹配：**
```python
# entity_resolution.py
from splink import Linker, SettingsCreator, comparing, block_on
settings = SettingsCreator(
    link_type="link_only",
    blocking_rules_to_generate_predictions=[
        block_on("email_domain"),        # 分块：避免笛卡尔积
        block_on("name", "institution"),
    ],
    comparisons=[
        comparing("name").distance("jaro_winkler"),
        comparing("institution").distance("jaccard"),
        comparing("email_domain"),
        comparing("research_fields").distance("jaccard"),
    ],
)
linker = Linker([authors_df, experts_df], settings, db_api)
# 三级匹配：精确规则 -> 模糊相似度 -> ML 概率
# match_weight > 阈值 => 合并；中间值 => 待人工复核
```

**冲突消解（字段级择优）：**

| 字段 | 主源 | 说明 |
|------|------|------|
| 姓名 | 专家名录 | 更规范 |
| 邮箱 | 论文库 | 更可能是工作邮箱 |
| 机构 | 时间新优先 | 两者留时间戳 |
| 研究方向 | 论文库 | 摘要更真实 |
| 职称/电话 | 专家名录 | 更准确 |

**验收**：persons 表含 `sources`（如 `['paper_db','expert_dir']`）和 `match_confidence`；抽样 100 条人工核对，精确召回达标再继续。

---

### P5 · Embedding 生成（硬件感知）

```python
# embed.py  —— 国内用 modelscope 拉模型
from modelscope import snapshot_download
model_dir = snapshot_download('BAAI/bge-m3')
from FlagEmbedding import BGEM3FlagModel
model = BGEM3FlagModel(model_dir, use_fp16=True)

# 低显存策略：batch_size 调小；若 OOM 退回 bge-large-zh-v1.5
texts = [row.research_summary for row in persons]
emb = model.encode(texts, batch_size=16, max_length=512)["dense"]

# 写回 persons.embedding
# UPDATE persons SET embedding = %s WHERE person_id = %s
```

- 本机低显存跑 100万：约 1–3 小时
- 全量 2200万：**交 Linux 服务器**，或临时云 GPU pod，跑完 `pg_dump` 向量表导回

**验收**：persons.embedding 非空率 > 99%；抽样 5 人做"找相似人"肉眼确认质量。

---

### P6 · 向量索引 + 混合检索 API

```sql
-- 建 HNSW 索引（检索快）
CREATE INDEX ON persons USING hnsw (embedding vector_cosine_ops);
```

```python
# api.py  (FastAPI)
@app.post("/search")
def search(q: str):
    filters, semantic = llm_parse(q)          # P7 的 LLM 解析
    # 结构化路
    sql = build_sql(filters)                  # city/institution/paper_count 等
    candidates = run_sql(sql)
    # 语义路
    q_emb = model.encode([semantic])["dense"]
    sim = vector_search(q_emb, top_k=200, scope=candidates)
    # 融合排序
    return rank(filters, sim)
```

**验收**：/search 接口单条查询 < 2 秒（含 LLM 解析 ~1s）；返回结构化 + 语义混合结果。

---

### P7 · 自然语言查询引擎（LLM 解析）

**LLM 的 system prompt（查询解析器核心）：**
```
你是一个人才检索系统的查询解析器。把用户自然语言拆成两部分：
1. structured_filters (JSON)：支持 city / institution / field / paper_count_min / h_index_min / email_domain
2. semantic_query (文本)：无法用字段表达的研究主题，并做查询扩展
示例：
用户："找研究大模型推理加速的专家，最好在北京"
→ {"structured_filters":{"city":"北京","paper_count_min":5},
   "semantic_query":"大模型推理加速 量化压缩 KV-Cache 投机解码"}
```

- 接入 Qwen-Max / DeepSeek（国内稳）或 GPT-4o（走代理）
- 测试集：纯结构化 / 纯语义 / 混合 / "和张三类似的人" 各 2–3 条

**验收**：10 条测试查询解析正确率 ≥ 90%；混合检索结果人工满意。

---

### P8 · 前端界面（MVP）

用 **Streamlit** 最快（比 React 省事，适合内部工具）：
```python
# app.py
import streamlit as st, requests
q = st.text_input("用自然语言描述你想找的人才：")
if q:
    res = requests.post("http://localhost:8000/search", json={"q":q}).json()
    for r in res:
        st.markdown(f"### {r['name']} · {r['institution']}")
        st.caption(f"匹配度 {r['score']:.2f} | 来源 {r['sources']}")
        st.write(r['research_summary'][:200])
```
`streamlit run app.py`

**验收**：浏览器打开能输入自然语言、返回人才卡片。

---

### P9 · 验收与交付

- **验收查询集**（覆盖 4 类）：纯结构化、纯语义、混合、相似人各 2–3 条
- 人工抽查准确率/召回，写验收报告
- 输出 README（环境搭建 + 跑数命令 + 常见问题）+ 交接给实习生
- 全量上线决策：样本验收通过后，用 Linux 服务器跑 P3–P5 全量，P6–P8 复用

---

## 四、风险与对策

| 风险 | 对策 |
|------|------|
| 低显存跑 BGE-M3 OOM | batch 降到 8；退回 bge-large；或全量交服务器 |
| HuggingFace 被墙 | 用 modelscope 镜像拉模型 |
| 作者消歧不准 | 先宽松合并，保留 aliases + confidence，前端可二次筛选 |
| 全量 2200万本机跑不动 | 样本验证后全量强制上 Linux 服务器 |
| LLM 解析偶发错误 | 解析结果做 schema 校验，失败时回退纯语义检索 |

## 五、下一步

确认本方案后，我们从 **P0 环境检测** 开始，你先跑 `nvidia-smi` 和 `wmic` 那几条命令，把输出贴给我，我据此确认 WSL2 / Docker / 显卡驱动的具体安装步骤。
