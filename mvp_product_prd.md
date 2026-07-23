# 全球人才精准匹配平台首期 MVP 产品需求文档

> 状态：范围已冻结  
> 文档类型：产品需求文档（PRD）  
> 基线日期：2026-07-22  
> 输入依据：现有能力盘点、数据底座与关系网络设计、系统开发方案，以及逐项产品与技术决策访谈  
> 适用范围：`relationship_network` 商业产品仓库与 CombineDatabase 检索底座之间的首期产品建设

## Problem Statement

当前 CombineDatabase 已经具备“学者名录与论文数据进入统一人物模型、论文向量检索、结构化检索、自然语言找专家”的数据与检索能力，但它仍是内部验证工具，不能作为客户可注册、可协作、可付费、可审计的商业产品使用。

目标客户包括猎头公司、人才服务机构和企业 HR 部门。他们目前面对的主要问题是：人才数据分散、职位需求难以转成可执行检索条件、候选人筛选缺少统一解释、团队协作依赖线下表格、报告制作成本高、联系方式和数据导出缺少权限与额度控制、平台也无法准确核算模型成本和客户用量。

首期产品需要把现有检索能力包装成一个完整的多租户业务系统。用户应能够创建组织、配置角色与权限、维护企业和职位、解析 JD、发起可追溯的人才匹配、管理人才池、生成深度报告、查看和导出授权范围内的联系方式，并完成试用、订阅、用量、通知和反馈闭环。

本项目不重新建设论文 ETL、人物聚类、论文向量和 OpenSearch 检索。商业产品必须站在现有 CombineDatabase 能力上扩展，同时解决现有检索接口尚未版本化、人物外部 ID 可能变化、可执行筛选字段有限等适配问题。

## Solution

建设一个中文桌面 Web 版全球人才精准匹配平台。产品采用“独立商业产品服务 + 现有检索底座”的架构：

- 商业产品负责认证、租户、动态 RBAC、企业、职位、匹配运行、人才池、报告、订阅、计费、用量、通知、反馈、隐私流程和平台运营。
- CombineDatabase 继续负责人物与论文数据、结构化查询、论文向量检索、rerank 和人物聚合。
- 商业产品通过受保护、版本化的内部 API 调用检索底座，不直接访问或修改 OpenSearch。
- 生成式 LLM 统一通过 OpenRouter 调用，默认模型为 `x-ai/grok-4.5`，模型名称和参数通过可发布配置管理。
- 论文 Embedding 和 rerank 首期继续使用现有 DashScope 能力，不重新生成全部向量。
- 商业业务数据保存在 PostgreSQL；异步任务使用 Redis 与 Celery；上传文件、报告和导出文件保存在 S3 兼容私有对象存储。
- 前端提供租户工作台和平台运营后台，首期交付所有核心流程的最小可用界面，而不是空框架。

产品首先让用户完成“注册与创建租户 → 创建企业与职位 → 上传并确认 JD → 发起匹配 → 筛选并管理候选人 → 解锁和导出联系方式 → 生成报告 → 查看用量和订阅”的完整闭环。

## User Stories

1. As a new customer, I want to register with a normal email address, so that I am not blocked by an enterprise-email requirement.
2. As a new customer, I want to verify my email address, so that my account cannot be created with an email I do not control.
3. As a new customer, I want to create a tenant during registration, so that my organization has an isolated workspace.
4. As a tenant creator, I want to become the protected tenant owner automatically, so that I can administer every current and future tenant capability.
5. As a tenant owner, I want the system to prevent removal of the final owner, so that the tenant cannot become unmanageable.
6. As a tenant owner, I want to invite members by email, so that only approved users can join my tenant.
7. As an invited member, I want to accept a time-limited single-use invitation, so that joining a tenant is secure and intentional.
8. As a user, I want to reset my password and revoke sessions, so that I can recover from lost credentials or suspected compromise.
9. As a platform administrator, I want MFA to be mandatory, so that high-privilege platform access has additional protection.
10. As a tenant owner, I want to require MFA for all tenant members, so that my organization can enforce a stronger security policy.
11. As a tenant owner, I want to create custom roles, so that access control matches my organization structure.
12. As a tenant owner, I want to assign system-defined permissions to a role, so that roles remain configurable without inventing unsupported permissions.
13. As a tenant owner, I want to assign multiple roles to one user, so that the user receives the union of the required capabilities.
14. As a tenant member, I want every operation to be checked against my effective permissions, so that hidden UI controls are not the only protection.
15. As a tenant member, I want all tenant data isolated from other tenants, so that no query, export, background job or file URL leaks cross-tenant information.
16. As a tenant owner, I want to create and maintain multiple client companies, so that a recruiting or talent-service organization can serve several customers.
17. As an enterprise HR tenant, I want to use a company record for my own organization, so that the same model supports direct employers.
18. As a recruiter, I want to create multiple jobs under a company, so that each hiring requirement has an independent lifecycle.
19. As a recruiter, I want job states for draft, active, paused and closed, so that only active jobs can launch new matching runs.
20. As a recruiter, I want companies and jobs to be archived rather than permanently deleted, so that historical matches and reports retain their context.
21. As a recruiter, I want to paste company and JD text directly, so that simple requirements do not require a file upload.
22. As a recruiter, I want to upload PDF, DOCX or TXT files up to 10 MB, so that common company and JD documents can be processed.
23. As a recruiter, I want uploaded files stored privately, so that tenant documents are not accessible through public URLs.
24. As a recruiter, I want the system to extract text from uploaded files, so that OpenRouter can parse the requirement.
25. As a recruiter, I want to edit extracted text when parsing fails, so that file-processing problems do not block job creation.
26. As a recruiter, I want OpenRouter to produce a structured JD draft, so that unstructured requirements become executable conditions and a semantic research query.
27. As a recruiter, I want to review and edit the parsed JD before activating the job, so that an LLM interpretation never becomes an unreviewed business rule.
28. As a recruiter, I want each confirmed JD to become an immutable version, so that historical matching runs remain reproducible.
29. As a recruiter, I want supported hard conditions to be used automatically, so that reliable structured data reduces the candidate set.
30. As a recruiter, I want unsupported JD conditions shown as not participating in matching, so that the system does not silently imply that it evaluated unavailable data.
31. As a recruiter, I do not want unsupported conditions to create manual-review tasks, so that job activation remains lightweight.
32. As a tenant user, I want a standalone natural-language talent search, so that I can explore the data without first creating a job.
33. As a tenant user, I want to see the interpreted structured and semantic intent for a natural-language search, so that I understand how the system searched.
34. As a tenant user, I want a successful natural-language search to consume one search unit rather than charge by result count, so that usage is predictable.
35. As a recruiter, I want to launch a matching run from an active job, so that the system returns job-specific candidates.
36. As a recruiter, I want every matching run saved independently, so that rerunning after a JD change does not overwrite history.
37. As a recruiter, I want a matching run to store the JD version, data version, algorithm version, model version and evidence, so that results are auditable.
38. As a recruiter, I want hard filters applied before scoring, so that candidates failing reliable mandatory requirements are not promoted by semantic similarity.
39. As a recruiter, I want candidate scoring produced by deterministic algorithms rather than an LLM opinion, so that scores can be reproduced and compared.
40. As a recruiter, I want matching explanations grounded in actual conditions, metrics and publications, so that explanations do not invent evidence.
41. As a recruiter, I want up to 500 candidates recalled, the top 100 persisted and the top 50 shown by default, so that results remain useful and manageable.
42. As a recruiter, I want low-relevance candidates omitted even when fewer than 100 remain, so that the system does not fill the list with noise.
43. As a platform operator, I want matching weights controlled by immutable platform algorithm versions, so that score meaning stays consistent across tenants.
44. As a recruiter, I want the product to use a stable local talent ID, so that external clustering changes do not break my talent pool or reports.
45. As a platform operator, I want external current and historical person IDs mapped to the local talent ID, so that data refreshes can reconcile identity changes.
46. As a recruiter, I want current talent details refreshed while historical match snapshots stay unchanged, so that I can see both current information and past evidence.
47. As a recruiter, I want a tenant-level talent record, so that tags, favourites and shared notes can be reused across jobs.
48. As a recruiter, I want a separate job-candidate record, so that status, owner and job-specific notes do not leak between different jobs.
49. As a recruiter, I want matching results added to the talent pool only when selected, so that hundreds of unreviewed results do not pollute the working pool.
50. As a team member, I want candidate status, owner, tags and notes to retain history, so that collaboration decisions are traceable.
51. As a recruiter, I want the same talent matched in multiple runs to remain one job candidate, so that repeated runs do not create duplicates.
52. As a paid tenant user with permission, I want to unlock a matched candidate's full contact information, so that I can contact an approved candidate.
53. As a tenant owner, I want contact access controlled by subscription, permission, match origin and quota, so that full personal information is not exposed indiscriminately.
54. As a paid tenant user, I want the same talent to consume contact-unlock quota only once per tenant, so that repeated access does not duplicate charges.
55. As a paid tenant user with export permissions, I want to export all full contact information within my visible scope, so that I can perform authorized offline work.
56. As a paid tenant user, I want a batch export to preview how many new unlocks it will consume, so that I can confirm the quota impact before generating the file.
57. As a platform administrator, I want to view full contact information by default, so that I can operate and support the data platform.
58. As a platform administrator, I want to batch export full contact information by default, so that platform-level operational data can be processed.
59. As an authorized exporter, I want XLSX and CSV files generated asynchronously, so that large exports do not block the browser request.
60. As an authorized exporter, I want download links to expire after 24 hours, so that old links do not remain indefinitely usable.
61. As a recruiter, I want to generate a report for a specific talent and job, so that the recommendation is grounded in the actual hiring context.
62. As a recruiter, I want each report tied to a job version, match run, talent snapshot and evidence snapshot, so that it can be reproduced and audited.
63. As a recruiter, I want a failed report generation to consume no quota, so that platform failures do not reduce my entitlement.
64. As a recruiter, I want reports displayed on the web and exportable as PDF, so that I can review online and deliver a formal artifact.
65. As a recruiter, I want report versions to be immutable, so that a regenerated report does not rewrite an earlier conclusion.
66. As a recruiter, I want reports to identify unsupported conditions and evidence gaps, so that missing data is not represented as a positive match.
67. As a recruiter, I do not want the report to determine talent-program eligibility, mobility intent or willingness to relocate, so that unsupported subjective conclusions are avoided.
68. As a tenant owner, I want a 14-day trial with limited search, matching and report quotas, so that I can evaluate the product without payment credentials.
69. As a tenant owner, I want a monthly subscription with explicit seats, active-job, search, match, report and contact-unlock entitlements, so that usage limits are understandable.
70. As a tenant owner, I want published plan versions to remain immutable, so that the platform cannot silently change my active subscription terms.
71. As a platform administrator, I want to create plans and publish new plan versions, so that prices and quotas can evolve safely.
72. As a platform administrator, I want to record offline payment and activate a subscription manually, so that the first release can operate without a payment merchant account.
73. As a platform administrator, I want to compensate incorrect usage with a reason and audit trail, so that billing errors can be corrected without modifying history.
74. As a tenant owner, I want successful actions to consume quota and failed or idempotently retried actions not to consume quota, so that metering is fair.
75. As a tenant owner, I want to view business usage units rather than raw model tokens and provider cost, so that product quotas remain understandable.
76. As a platform administrator, I want to view token usage, provider cost and latency by tenant and task, so that I can monitor margin and anomalies.
77. As an expired tenant user, I want to log in, view and export existing data indefinitely, so that subscription expiry does not erase prior work.
78. As an expired tenant user, I do not want to create or modify business data, run searches, launch matches, generate reports or unlock contacts, so that the product enforces read-only expiry.
79. As a tenant owner, I want resubscription to restore the existing roles and data, so that I can resume work without rebuilding the tenant.
80. As a user, I want in-app notifications for important account, task, quota, subscription and assignment events, so that I can track work without polling.
81. As a user, I want email notifications for important events, so that I can receive updates outside the product.
82. As a user, I want ordinary business emails configurable while security and billing messages remain mandatory, so that preferences do not suppress critical notices.
83. As a recruiter, I want to mark a candidate suitable, unsuitable or uncertain and record a reason, so that the platform accumulates evaluation data.
84. As a report consumer, I want to mark a report helpful or unhelpful, so that report quality can be assessed.
85. As a platform operator, I want feedback used for offline evaluation rather than immediate online learning, so that one user's error cannot change all tenants' rankings.
86. As a user, I want to report duplicate people, incorrect merges, outdated institutions or incorrect contacts, so that data defects enter a managed queue.
87. As a platform administrator, I want to set a master local talent record and aliases, so that duplicate product records can be reconciled without rewriting history.
88. As a user, I want to consent to a versioned privacy policy and service terms, so that the platform records the terms I accepted.
89. As a data subject, I want to submit correction, deletion or objection requests, so that I can exercise rights over information about me.
90. As a tenant owner, I want to request tenant-data export or permanent deletion, so that my organization controls its retained business data.
91. As a platform administrator, I want a minimal operations console separated from tenant routes, so that tenant support, subscriptions, quotas and failed jobs can be managed safely.
92. As a platform administrator, I want high-risk mutations and exports audited for at least two years, so that operational changes are traceable.
93. As a platform administrator, I do not require an audit event for merely opening a single talent's contact details, so that the approved operating policy is preserved.
94. As a system operator, I want OpenRouter requests restricted to zero-data-retention endpoints and providers that do not collect data, so that prompts are not retained for training or provider logging.
95. As a system operator, I want OpenRouter raw responses encrypted and retained for 90 days, so that production issues can be investigated without indefinite raw-response retention.
96. As a system operator, I do not want complete assembled prompts stored, so that JD and talent data are not duplicated in application logs.
97. As a system operator, I want cross-model fallback to require an explicit configuration release, so that task behavior does not silently change.
98. As a user, I want clear failure states and notifications when OpenRouter or the search service is unavailable, so that the product never fabricates results.
99. As a user, I want failed asynchronous jobs retried and failed quota reservations released, so that transient failures do not produce duplicate work or charges.
100. As a system operator, I want every search and match to record the actual data-index version, so that later data refreshes do not invalidate historical interpretation.

## Implementation Decisions

### Product and repository boundary

- The commercial product is built as an independent repository. The existing data pipeline and OpenSearch implementation remain in CombineDatabase.
- The commercial product depends on a versioned internal search contract. Business modules do not construct OpenSearch DSL and do not write to search indexes.
- The CombineDatabase integration must add service authentication, explicit request and response schemas, request IDs, timeouts, model/index metadata, batch person lookup and evidence lookup.
- Existing internal search endpoints may remain for compatibility, but the commercial product uses a new versioned internal API.

### Application architecture

- The backend is a modular monolith with one API deployment and one PostgreSQL database. Domain modules communicate through application-service interfaces rather than modifying each other's storage directly.
- A separate asynchronous worker handles file extraction, matching, reports, notifications and exports.
- Redis is a queue and cache, never the sole source of business truth.
- PostgreSQL stores transactional business data; S3-compatible private object storage holds uploads, report files and exports.
- The frontend is one Next.js application with strict route separation between the tenant application and platform operations console.

### Technology baseline

- Backend: Python 3.12, Poetry, FastAPI, Pydantic, SQLAlchemy and Alembic.
- Frontend: Next.js, React, TypeScript, Bun, shadcn/ui and Tailwind CSS.
- Infrastructure: PostgreSQL 16, Redis, Celery, MinIO/S3, Nginx and Docker Compose.
- Windows development runs Poetry and Bun on the host while infrastructure runs in Docker Desktop. Production runs on Linux.
- Configuration is environment-driven and contains no hard-coded Windows paths or secrets.
- Source control uses a private GitHub repository and Linux-based GitHub Actions.

### Tenant, account and RBAC model

- A tenant represents a subscribing customer organization. A tenant owns companies, jobs, match runs, talent-pool data, reports, subscriptions and usage.
- Registration accepts normal email addresses. The first user creates a tenant and receives the protected `tenant_owner` system role.
- A tenant always has at least one owner. The owner role cannot be edited or deleted and automatically receives future permissions.
- Additional members join through time-limited, single-use invitations.
- One user belongs to one tenant in the first release, while the data model may leave room for future multi-tenant membership.
- System-defined permissions use business-action granularity. Tenants create custom roles, assign permissions to roles and assign one or more roles to users. Effective permissions are the union of assigned roles.
- Permission groups cover tenant settings, members, roles, companies, jobs, matching, talent pool, reports, billing, usage, feedback, notifications, contact reveal and exports.
- Authorization is enforced on the server. The frontend never acts as the sole access-control boundary.
- Every tenant table has a required tenant identifier. Application-scoped filtering and PostgreSQL RLS jointly enforce isolation. Background jobs restore tenant context before accessing data.

### Authentication and MFA

- Browser sessions use secure HttpOnly cookies, short-lived access sessions and rotating refresh sessions.
- Password changes, account suspension and tenant removal revoke relevant sessions.
- Registration, login, password reset, invitation acceptance and refresh endpoints are rate limited.
- Platform administrators must use TOTP MFA. Tenant users may enable MFA, and a tenant owner may require MFA for all members.
- MFA recovery codes are one-time values whose verifiers are stored securely.

### Company, job and document model

- A tenant owns many companies; a company owns many jobs.
- Jobs use draft, active, paused and closed states. Only active jobs launch matching runs.
- Companies and jobs use soft deletion or archival to preserve historical references.
- Company profiles and JDs accept text, PDF, DOCX and TXT, with a 10 MB file limit.
- Files are type-validated, malware-checked and stored privately. Extracted text, source file and parsing version are retained.
- OpenRouter creates a structured requirement draft. Users must review and confirm it before activation.
- Confirmed requirements are immutable versions. Matching runs bind to a specific version.
- Supported conditions execute automatically. Unsupported conditions remain in the snapshot and are displayed as not participating, but do not create manual-review work.

### OpenRouter integration

- OpenRouter is the only provider for new generative LLM tasks in the first release. The default configured model is `x-ai/grok-4.5`.
- JD parsing, matching explanations, report generation and new natural-language interpretation use a shared provider adapter.
- Model identifiers, request parameters and task-specific model assignments are configuration versions, not hard-coded constants.
- Production requests enforce zero-data-retention routing, deny data collection and require providers to support all parameters used by structured tasks.
- Structured tasks use strict JSON Schema outputs.
- OpenRouter may route between compliant upstream endpoints serving the same model. Cross-model fallback requires an explicit platform configuration release and regression evaluation.
- LLM call records store provider, actual upstream provider, model, prompt-template version, generation ID, request ID, input/output/reasoning tokens, cost, latency and error information.
- Parsed structured results and final reports are retained with business data. Complete raw model responses are encrypted and deleted after 90 days. Complete assembled prompts are not stored.
- Existing DashScope publication Embedding and rerank remain unchanged in the first release.

### Search and matching

- Standalone natural-language search is included. Successful natural-language searches consume one `nl_search` unit regardless of result count.
- A matching run is immutable and stores its requirement version, data version, algorithm version, model version, query plan, evidence, status and initiator.
- The matching pipeline applies reliable hard filters, retrieves up to 500 candidates, performs publication-vector retrieval and rerank, aggregates evidence to people, computes deterministic scores, persists up to 100 candidates and displays 50 by default.
- Low-relevance results are omitted rather than padded to the target count.
- The initial score weights are semantic relevance 50%, preference satisfaction 20%, academic impact 20%, and data completeness/freshness 10%.
- LLMs parse requirements and explain evidence; they do not assign the final score.
- Weight configurations are immutable platform algorithm versions. Tenants cannot customize weights in the first release.
- Supported structured person filters initially include institution rankings, Chinese identity, country, current affiliation, h-index and total citations. Research topics use publication-vector retrieval.

### Stable talent identity and data refresh

- The product creates its own stable local talent identifier instead of using the external canonical person identifier as a business primary key.
- External current IDs, historical IDs, source, sync status and last synchronization time are stored in a mapping layer.
- Match candidates, talent pools and reports refer to the local identifier.
- Historical matches and reports preserve snapshots. Current talent details may be refreshed without rewriting historical artifacts.
- Data is published from CombineDatabase as validated versions with no fixed update schedule. Product artifacts record the actual data version and display the latest known update time.
- If an external person disappears, the local record remains and is marked as temporarily unavailable.

### Talent pool and collaboration

- `tenant_talent` represents a tenant's reusable talent record, including shared tags, favourites and public notes.
- `job_candidate` represents a talent in one job, including stage, owner, job-specific notes, score and source match runs.
- The candidate stages are pending review, shortlisted, contacted, communicating, interviewing, hired, rejected and archived.
- Match results do not automatically enter the talent pool. A user must explicitly add or shortlist them.
- One talent has at most one candidate record per job; multiple match-run sources remain linked.
- Status, assignment, tags and notes retain business history. Normal users archive rather than permanently delete candidate data.

### Contact access and exports

- Non-entitled users see masked contact information.
- Tenant access to full contacts requires an active paid subscription, a matched and pooled talent, `contact.reveal`, and available contact-unlock quota.
- One tenant unlocks one talent once. Later viewing does not consume additional quota.
- Batch exports may unlock multiple talents after showing the count and quota impact and receiving confirmation. Quota consumption and unlock creation are atomic.
- Tenant exports require both talent-pool export and contact-reveal permissions.
- Platform administrators may view and batch export full contacts by default. Opening one contact detail does not create an audit event under the approved operating policy.
- Contact unlocks and full-contact exports are audited. Export jobs retain creator, time, filters and status.
- XLSX and CSV are supported. Exports use fixed safe field templates, run asynchronously, allow at most 50,000 rows per file and use private links that expire after 24 hours.

### Reports

- A report binds tenant, company, job, requirement version, talent, match run, evidence snapshot, report-template version, prompt version and model version.
- Reports are immutable. Regeneration creates another version.
- Reports are generated asynchronously and use queued, running, completed and failed states.
- Failed generation consumes no report quota.
- The report source is structured data plus rendered Markdown/HTML. Users view reports in the product and export PDF. Word and PowerPoint are not supported.
- Reports cover overview, overall conclusion, executable hard-condition results, research fit, academic impact, institution/country/Chinese-identity information, evidence publications, missing data, unsupported conditions, recommended follow-up questions, version metadata and disclaimer.
- Reports do not determine talent-program eligibility and do not present mobility, relocation or willingness assumptions as facts.

### Plans, subscriptions, billing and usage

- Plan entitlements cover seats, active jobs, natural-language searches, matching runs, reports and contact unlocks.
- New tenants receive one 14-day trial with one owner seat, one company, two active jobs, 20 searches, three matching runs and one report.
- Plans are versioned. Published plan versions are immutable, and active subscriptions retain their entitlement snapshot until explicit migration or renewal.
- The first release implements monthly subscriptions. Base quotas reset each subscription period and do not roll over. Purchased report packs remain valid for 12 months.
- Successful operations consume quota. Failed tasks, retries of the same idempotent request and administrator compensation do not double-charge.
- Usage is recorded in an append-only ledger, not only as mutable counters.
- Formal prices remain configurable and are published before production launch.
- No payment merchant account is currently available. The first release supports offline payment confirmation and manual subscription activation. Payment-provider and webhook contracts are reserved for later adapters.
- Invoice application is not included; only extension points are reserved.
- On expiry, the tenant enters permanent read-only mode. Existing companies, jobs, talent-pool data and reports remain visible and exportable. No new search, match, report, unlock or mutation is allowed. Resubscription restores write capabilities.
- Tenant users see business usage units. Platform administrators see provider tokens, costs and latency for cost and margin analysis.

### Platform operations

- Platform administration uses a separate route area and server-side authorization path from tenant features.
- Platform administrators manage tenants, plan versions, offline orders, subscription activation, usage compensation, job failures, notification tasks and data-quality cases.
- Platform administrators do not automatically become tenant members.
- Access to tenant business data for support is separately controlled. Full-contact access follows the explicit platform policy above.

### Notifications, feedback and data quality

- Business modules publish events; they do not send email directly.
- Notification workers create in-app notifications and send email asynchronously with retry and idempotency.
- Events cover invitations, role changes, password reset, match/report completion or failure, usage thresholds, subscription events and candidate assignment.
- Users may disable ordinary business emails but not critical security, account and billing messages.
- Candidate feedback supports suitable, unsuitable and uncertain, reason categories and optional comments. Report feedback supports helpful/unhelpful and issue categories.
- Feedback is tenant-private and feeds offline evaluation. It does not change online rankings automatically.
- Data-quality feedback creates cases for duplicate talents, incorrect merges, outdated affiliations, incorrect contacts and other defects.
- Platform administrators may map aliases and select a master local talent record. Historical results remain immutable.

### Privacy, audit and retention

- Registration records acceptance of versioned service terms and privacy policy.
- Talent pages show source information and expose correction, deletion and objection request entry points.
- Tenant owners can request tenant export or permanent deletion.
- Security events, role changes, business archival, match/report launches, contact unlocks, exports, billing changes, usage compensation, support access and deletion actions are audited.
- Audit records are append-only and retained for at least two years.
- The approved exception is that platform administrators opening a single talent's contact details do not generate an audit event.
- Application logs, analytics and notifications must not contain passwords, tokens or full contact information.

### Deployment and operational targets

- Development occurs on Windows in the commercial-product repository. Production runs on Linux with Docker Compose, Nginx, a formal domain and HTTPS.
- PostgreSQL and object storage are backed up automatically. Database transaction-log archiving targets an RPO of 15 minutes and an RTO of four hours.
- Daily full backups are retained for at least 30 days, and recovery is exercised quarterly.
- The initial capacity target is 50 active tenants, 500 registered users, 50 concurrent online users, 10 simultaneous matching jobs and five simultaneous report jobs.
- Ordinary API P95 is under 500 ms, natural-language search P95 under 10 seconds, matching completes within five minutes and report generation within 10 minutes under the target load.
- External-service failures produce explicit states, retries and notifications. They never produce fabricated results or relax privacy routing.

### Delivery sequence

1. Repository, Poetry, Next.js/Bun, Docker infrastructure and CI.
2. Authentication, tenant, dynamic RBAC, MFA and platform administrator.
3. Plan versions, trial, subscription, entitlement checks, usage ledger and offline orders.
4. Company, job, upload, OpenRouter parsing and requirement confirmation.
5. Versioned CombineDatabase internal API, local talent identity, natural-language search and matching runs.
6. Tenant talent records, job candidates, owners, tags, notes and history.
7. Contact permissions, batch unlock and XLSX/CSV export.
8. Deep reports, web rendering and PDF export.
9. Notifications, feedback, data-quality and privacy requests.
10. Capacity, security, recovery, Linux deployment and full acceptance.

Each stage includes backend behavior, a minimal usable frontend, migrations, authorization checks, automated tests and an actual user-flow demonstration.

## Testing Decisions

### Testing philosophy and seams

- Tests assert externally observable behavior, authorization results, persisted business state and user-visible outcomes rather than private function structure.
- The preferred highest seam is the complete browser-to-API-to-database flow, with external LLM, search, email and object-store boundaries replaced by contract-faithful test adapters where deterministic control is needed.
- Lower-level unit tests are used for deterministic score computation, permission resolution, state transitions, quota accounting, data normalization and serialization. They do not replace end-to-end acceptance evidence.
- Search integration uses contract tests against the versioned internal API and a real integration environment before release.
- Existing CombineDatabase unit tests and fixture-based pipeline/search smoke tests are prior art for data and retrieval behavior; the commercial product adds transactional and browser-level seams.

### Required module coverage

- Authentication: registration, verification, invitation, login, refresh rotation, password reset, session revocation and MFA.
- RBAC: custom roles, multi-role union, owner protection, every permission allow/deny pair and server-side enforcement.
- Tenant isolation: cross-tenant reads, writes, exports, background jobs and signed object URLs must fail.
- Companies/jobs: state transitions, soft deletion, upload validation, parsing failure, user confirmation and immutable requirement versions.
- OpenRouter: strict schema, ZDR routing configuration, metadata capture, raw-response retention, timeout, retry and no silent cross-model fallback.
- Search/matching: query-contract compatibility, supported/unsupported conditions, deterministic scoring, result limits, evidence, snapshots and algorithm versions.
- Talent identity/pool: external-ID changes, alias mapping, one candidate per job, multi-run provenance, status/assignment/note history and archival.
- Contacts/exports: masking, paid entitlement, permission, matched-and-pooled scope, atomic batch unlock, idempotent quota, platform policy, row limits and expiring links.
- Reports: evidence snapshots, immutable versions, async states, failure without quota charge, web rendering and PDF generation.
- Billing/usage: trial, monthly resets, immutable plans, offline orders, subscription transitions, read-only expiry, append-only ledger and compensation.
- Notifications: event idempotency, retries, preference rules and mandatory-message exceptions.
- Feedback/data quality: tenant isolation, offline-only learning behavior, issue workflow and master/alias reconciliation.
- Privacy/audit: consent versions, requests, deletion flow, required audit events, the platform contact-view exception and retention.
- Operations: backup creation is insufficient by itself; restoration must be exercised and verified.

### Final end-to-end acceptance scenarios

1. Register, verify email, create a tenant and receive the trial and owner rights.
2. Create a custom role, assign permissions, invite a member and prove denied operations are blocked.
3. Create a company and job, upload a JD, parse it with OpenRouter and confirm a requirement version.
4. Run natural-language search and record exactly one successful search unit.
5. Launch matching and produce an immutable run with at most 100 candidates and evidence-backed scores.
6. Add candidates to the two-layer talent pool and collaborate with status, owner, tags and notes.
7. Activate a paid subscription, batch unlock matched contacts and export authorized full contact information.
8. Generate an immutable evidence-backed report and export PDF.
9. Confirm an offline order, activate subscription, compensate usage and inspect provider cost in the platform console.
10. Cause OpenRouter or search failure and prove retry, notification, explicit failure state and no duplicate charge.
11. Submit match feedback and a data-quality issue and resolve the issue through the platform queue.
12. Expire a subscription, prove permanent read-only behavior, then resubscribe and restore writes.
13. Attempt cross-tenant read, mutation and export and prove every path is denied.
14. Meet the agreed load target, restore from backup and deploy the same release to Linux.

### Definition of done for each delivery stage

- Migrations apply from an empty database and have a safe repair or forward-migration strategy.
- Backend unit and PostgreSQL integration tests pass.
- Frontend type checking, unit tests and production build pass.
- Playwright covers the new real-user flow and meaningful denial paths.
- RBAC and tenant-isolation tests cover both allowed and forbidden behavior.
- Async jobs cover success, failure, retry, idempotency and quota release.
- Chrome and Edge receive real visual checks for changed pages.
- Windows development and Linux Docker environments both start successfully.
- API, permissions, domain model and operational behavior are documented.

## Out of Scope

- Co-author graph construction, Neo4j, one-hop or two-hop recommendations, centrality and community detection.
- Talent-program eligibility determination.
- Automated new-talent alerts driven by data updates.
- Automatic online learning or automatic modification of ranking weights.
- External ATS/HR-system API.
- Multi-language UI.
- Native mobile applications.
- Automated outbound calling, bulk outreach email and contact scripts.
- Field-level RBAC beyond the explicitly defined contact permissions.
- One user joining multiple tenants.
- Word or PowerPoint report export.
- Multiple live payment channels in the first release.
- Live payment integration until a valid merchant account exists.
- Invoice application and tax-system integration.
- Kubernetes.
- Splitting the commercial backend into ten microservices.
- Fixed weekly or other scheduled data refresh guarantees.
- Replacing the existing DashScope publication Embedding and rerank or re-vectorizing the whole corpus.

## Further Notes

### Confirmed external prerequisites that do not block development

- Formal plan prices and production quota values are configured before launch.
- Payment-channel implementation waits for a valid merchant account.
- Production email provider, Linux server specification, domain and OpenRouter production key remain deployment configuration.
- Data updates remain validated, versioned batches without a fixed publication cadence.

### Known adaptations and risks

- The existing natural-language search interface needs a stable, authenticated, versioned internal contract before commercial use.
- External canonical person identifiers are stable only when strong identifiers remain available; local stable IDs and alias reconciliation are mandatory.
- The current structured-search field set is narrower than a typical JD. Unsupported conditions must remain visible as non-participating and must never be represented as satisfied.
- Full-contact access and bulk export create a high-value data-exfiltration surface. MFA, permission checks, subscription and quota enforcement, private expiring files and export-task records are mandatory under the approved product policy.
- Platform administrators are intentionally allowed to view and batch export full contacts, and individual contact views intentionally do not create audit events. This is an explicit product decision and should be re-evaluated during legal and security review before launch.
- OpenRouter routing must keep ZDR and no-data-collection requirements enabled even during provider failure. Availability must not override the approved privacy boundary.

### Product release boundary

The MVP is complete only when the 14 final acceptance scenarios pass with evidence. The existence of APIs, green unit tests or a frontend shell alone does not satisfy the release goal.
