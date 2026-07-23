# 作者关系网络（合著图）· 数据模型与业务应用设计

> 解决：2000万论文的"作者"字段是多值，作者之间形成合著关系网。
> 目标：用数据库表达这张网，并支撑两大业务场景——
> ① 经合作教授推荐其他人申报人才计划；② 找到某牛人合作过的国内教授，便于中国落地。

---

## 一、本质：这是一张"属性图（Property Graph）"

- **节点（Node）= 人**：即 P3 聚合出的 author / 合并后的 person。
- **边（Edge）= 合著关系**：同一篇论文的两个作者之间连一条边。
- **边权重 = 合著论文数**：合作越多，关系越紧。
- 边的属性还可带：首次/最近合作年份、合作论文 id 列表。

合著关系天然是**无向**的（A 与 B 合著 = B 与 A 合著）。

---

## 二、两种物理落地方式

### 方案 A：PostgreSQL 边表（MVP，不引入新组件）

在已有 `persons` 表之外，加两张表：

```sql
-- 论文→作者 映射（P3 聚合时一并产出）
CREATE TABLE paper_authors (
  paper_id   TEXT,
  person_id  UUID,
  author_idx INT,
  PRIMARY KEY (paper_id, person_id)
);

-- 合著边表（无向，存双向镜像便于查询）
CREATE TABLE coauthor_edges (
  source_person_id   UUID,
  target_person_id   UUID,
  joint_paper_count  INT,
  first_year         INT,
  last_year          INT,
  PRIMARY KEY (source_person_id, target_person_id)
);
```

**写入双向镜像**（查询时不用管方向）：
```sql
INSERT INTO coauthor_edges (source_person_id, target_person_id, joint_paper_count)
SELECT a.person_id, b.person_id, COUNT(*)
FROM paper_authors a
JOIN paper_authors b
  ON a.paper_id = b.paper_id AND a.author_idx < b.author_idx
GROUP BY a.person_id, b.person_id;
-- 再 INSERT 一份 (target, source) 镜像，或查询时 UNION 两个方向
```

### 方案 B：Neo4j 图数据库（增强，深度遍历 / 中心性 / 社群发现）

当查询需要 **>2 跳**、或要做 **中心性（谁是最好的人脉桥梁）**、**社群发现（研究集群）** 时，原生图库远胜 SQL 递归。

```bash
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j=你的密码 neo4j:latest
```

建模（Cypher）：
```
(:Person {name, institution, country, citation_count, eligible_talent})
-[:COAUTHORED_WITH {joint_papers, last_year}]->
(:Person)
```

**何时上 Neo4j**：样本阶段先用方案 A 验证两个场景；当出现以下信号再引入——
- 边规模 > 5000万，2 跳以上递归在 PG 变慢；
- 需要做中心性 / 社群发现 / 影响力排序；
- 想给前端做"关系图谱可视化"。

> 数据同步：persons + coauthor_edges 由 PG 全量导出，用 `neo4j-admin import` 或 Python 驱动灌入 Neo4j，二者同源、定期刷新。

---

## 三、从 2000万论文生成边（规模估算）

- 2000万篇 × 平均 4 作者 ≈ 每篇 C(4,2)=6 对 → **约 1.2 亿条边**。
- 样本（100万篇）≈ 600万条边，PG 毫无压力。
- 全量 1.2亿边：PG 边表约 3–5GB；Neo4j 更擅长承载与遍历。
- 生成方式：样本用上面的 SQL；全量用 PySpark / DuckDB 分批聚合，避免单条 SQL 爆内存。

---

## 四、两个业务场景的查询实现

### 场景 2：找与某牛人合作过的"国内教授"（中国落地）

**PostgreSQL（已知 X 的 person_id = :xid）：**
```sql
SELECT p2.person_id, p2.name, p2.institution, p2.city,
       e.joint_paper_count, e.last_year
FROM coauthor_edges e
JOIN persons p2 ON e.target_person_id = p2.person_id
WHERE e.source_person_id = :xid
  AND p2.country = 'China'
ORDER BY e.joint_paper_count DESC, e.last_year DESC;
```

**Neo4j（Cypher）：**
```cypher
MATCH (x:Person {name:'X教授'})-[r:COAUTHORED_WITH]-(y:Person)
WHERE y.country = 'China'
RETURN y.name, y.institution, r.joint_papers
ORDER BY r.joint_papers DESC
```

> 含义：这些国内教授和 X 已有合作基础 → 是 X 成果在中国落地的天然桥梁（可联合实验室、共同申报、作挂靠单位）。

### 场景 1：经合作网络推荐人才申报计划

**思路**：取 X 的 1 跳合作者，再取其合作者（2 跳），过滤"符合人才计划资格"的人，按"被多少人可引荐（connect_paths）+ 本人成果"排序。

**PostgreSQL（2 跳推荐）：**
```sql
WITH direct AS (
  SELECT target_person_id AS pid
  FROM coauthor_edges WHERE source_person_id = :xid
  UNION
  SELECT source_person_id FROM coauthor_edges WHERE target_person_id = :xid
)
SELECT p.person_id, p.name, p.institution,
       COUNT(*) AS connect_paths
FROM coauthor_edges e
JOIN direct d ON (e.source_person_id = d.pid OR e.target_person_id = d.pid)
JOIN persons p ON p.person_id = CASE
       WHEN e.source_person_id = d.pid THEN e.target_person_id
       ELSE e.source_person_id END
WHERE p.person_id <> :xid
  AND p.eligible_talent = true          -- 符合人才计划申报资格
GROUP BY p.person_id
ORDER BY connect_paths DESC, p.citation_count DESC;
```

**Neo4j（带引荐路径，更直观）：**
```cypher
MATCH path = (x:Person {name:'X教授'})-[:COAUTHORED_WITH*1..2]-(z:Person)
WHERE x <> z AND z.eligible_talent = true
RETURN z.name, z.institution,
       [n IN nodes(path) | n.name] AS intro_path
ORDER BY length(path), z.citation_count DESC;
```

> 排序维度建议：`connect_paths`（越多合作者能引荐他，可信度越高）＋ `citation_count`（本人硬实力）＋ `joint_paper_count`（与引荐人的亲密度）。

---

## 五、进阶：用图算法放大价值

引入 Neo4j GDS 后还能做：

| 算法 | 业务价值 |
|------|----------|
| **度数中心性** | 找出"人脉最广"的教授 → 选他做合作桥梁，触达面最大 |
| **介数中心性** | 找出"连接两个集群的关键人" → 跨领域落地的最佳中间人 |
| **社群发现 (Louvain)** | 自动识别研究集群 → 按领域批量对接人才计划 |
| **PageRank** | 学术影响力排名 → 优先攻克高排名者 |

```cypher
CALL gds.degree.stream('coauthor-graph')
YIELD nodeId, score RETURN gds.util.asNode(nodeId).name, score
ORDER BY score DESC LIMIT 20;
```

---

## 六、与主干流水线的衔接

- **位置**：放在 **P3（作者聚合）之后、P4（双库合并）可一并打通**。合并后的 `persons` 与 `coauthor_edges` 用同一个 `person_id` 关联。
- **反向 enrich persons**：给 `persons` 加字段
  `collaborator_count`（合作者数）、`china_collaborator_count`（国内合作者数）、`network_centrality`（中心性分），让自然语言检索也能直接命中，例如：
  > "找和 XX 教授合作过的国内专家" → SQL：`... JOIN coauthor_edges ... WHERE target.country='China'`
- **自然语言能力增强**：把"关系网"作为一类可解析意图，LLM 解析出 `related_to: 'XX教授'` + `relation: 'coauthor'` + `filter: {country:'China'}`，路由到图谱查询。

---

## 七、规模与性能小结

| 规模 | 推荐存储 | 2 跳查询 | 深度/算法 |
|------|----------|----------|-----------|
| 样本 100万篇（~600万边） | PostgreSQL 边表 | 秒级 | 递归 CTE 足够 |
| 全量 2000万篇（~1.2亿边） | PG 边表（结构化过滤）+ Neo4j（图谱分析） | PG 直接邻居秒级；深遍历交 Neo4j | Neo4j GDS |

**结论**：MVP 阶段用 PostgreSQL 边表就能把两个场景跑通；把"关系网"当成项目的差异化资产，等样本验证有效、要上深度分析和可视化时，再引入 Neo4j。
