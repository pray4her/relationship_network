# [MVP-11] 建立检索底座版本化内部服务契约

父规格：#1  
领域决策：ADR 0025  
状态：范围已冻结，可独立实现

## Problem Statement

商业产品已经能维护租户、企业和职位需求版本，但还不能以稳定、可测试的方式读取检索底座中的规范人物、论文和人物证据。现有检索底座接口未认证、未版本化，且包含自然语言找专家等本产品不得依赖的能力。若商业模块直接查询其内部存储或沿用旧接口，匹配、人才池和报告将无法审计数据版本，也无法在无真实检索集群的 CI 中验收。

## Solution

在本仓库交付检索底座的消费者侧：冻结检索契约版本、服务端适配器、可独立运行的假检索底座，以及必须打真实适配器的契约测试。本产品 API 与 Worker 仅以服务身份调用；契约只认规范人物与当前数据版本，只执行硬条件与研究主题查询，返回检索命中与人物证据，不含完整联系方式，也不计算匹配总分。真实检索实现仍留在检索底座仓库。

## User Stories

1. As the commercial product API, I want to call the search base only with a service credential, so that tenant browsers cannot reach talent data directly.
2. As a worker process, I want to use the same search-base adapter as the API, so that later matching jobs do not invent a second client.
3. As a platform operator, I want tenant members and my personal admin session to be unable to call the search base, so that RBAC, quotas and contact gates stay inside this product.
4. As a platform operator, I want authentication failures to have a stable error category, so that operators can distinguish bad credentials from query problems.
5. As the commercial product, I want every request to carry a request identifier that the search base echoes, so that timeouts and partial failures can be traced.
6. As the commercial product, I want to declare a search-contract version on every call, so that incompatible providers fail closed instead of silently changing shape.
7. As a platform operator, I want contract-version mismatch to be a non-retryable error, so that retries do not hammer a provider that cannot serve this contract.
8. As the commercial product, I want data-version identifiers on every successful response, so that later match runs can record which published index they read.
9. As the commercial product, I want one successful read to use a single data version, so that a search hit and its fields are not mixed across publications.
10. As the commercial product, I want the search base to serve only the current data version, so that I do not treat a data version as a historical query key.
11. As a recruiter (later matching), I want historical interpretations to come from product snapshots, so that a newer index cannot rewrite an old score's evidence.
12. As the commercial product, I want search requests to send only hard conditions and a research topic query, so that preference conditions cannot exclude people at recall time.
13. As the commercial product, I want the adapter to reject preference conditions before HTTP, so that callers cannot accidentally filter on scoring-only rules.
14. As the commercial product, I want unsupported conditions to stay out of the search request, so that the search base is not asked to execute catalog-external fields.
15. As the commercial product, I want empty hard-condition lists to be valid when a research topic query is present, so that semantic-only recall remains possible.
16. As the commercial product, I want a missing or empty research topic query to be rejected, so that recall cannot run without a vector query.
17. As the commercial product, I want hard conditions to use the Schema v1 field catalog and operators, so that confirmed job requirement versions can be executed without translation.
18. As the commercial product, I want `chinese_identity` values limited to 国内华人, 海外华人 and 外国人, so that inferred identity filters stay inside the frozen catalog.
19. As the commercial product, I want unknown fields or operators to fail as invalid query, so that the product never claims a filter the search base cannot run.
20. As the commercial product, I want search hits identified by canonical person IDs plus known historical source IDs, so that later local talent mapping can survive merges.
21. As the commercial product, I want search hits to include current executable fields needed for later scoring, so that preference, impact and completeness scores can be computed in this product.
22. As the commercial product, I want each search hit to include a numeric semantic relevance signal and hit publication IDs, so that ranking inside one response is deterministic without a final match score.
23. As the commercial product, I want search hits within one response ordered by semantic relevance, so that callers can apply the 500/100/50 cutoffs later without re-querying.
24. As the commercial product, I want the adapter to request at most 500 hits, so that recall matches the frozen matching ceiling.
25. As the commercial product, I want search hits to omit full contact details, so that unlocking quota cannot be bypassed by search.
26. As the commercial product, I want an optional has-contact marker on current fields, so that later unlock flows can know whether a contact exists without receiving it.
27. As the commercial product, I want person detail by canonical person ID at the current data version, so that a talent page can hydrate without inventing a job query.
28. As the commercial product, I want batch person reads, so that hydrating many match hits does not require one request per person.
29. As the commercial product, I want batch reads to succeed when some IDs are absent from the current data version, so that a later refresh of 100 match hits is not aborted by three disappeared people.
30. As the commercial product, I want absent IDs listed as current absence, so that I do not confuse this outcome with a transport failure.
31. As the commercial product, I want the search base not to distinguish never-existed from previously-published-and-now-gone, so that the contract does not imply historical index retention.
32. As the commercial product, I want a whole-batch transport or auth failure to fail the batch, so that partial success is only for current absence, not for dropped connections.
33. As the commercial product, I want person evidence by canonical person ID without a search query, so that a dossier is stable across search, matching and later talent-pool views.
34. As the commercial product, I want person evidence to include publications and structured-field provenance, so that explanations can cite actual papers and field sources.
35. As the commercial product, I want person evidence to omit email and other full contact claims, so that evidence lookup is not a PII dump.
36. As the commercial product, I want hit publication IDs on a search hit to refer to publications that also appear in that person's evidence, so that hit papers are a subset of the dossier, not a second identity space.
37. As the commercial product, I want a search-base health endpoint, so that Compose, CI and the adapter can see whether the fake or real provider is reachable.
38. As a platform operator, I want search-base unavailability not to redefine platform health, so that homepage health remains API plus PostgreSQL, Redis and object storage.
39. As the commercial product, I want timeouts configured through RN_ settings, so that local, CI and production can share the adapter with different budgets.
40. As the commercial product, I want retries only on safe reads, so that a confused POST is not replayed as a side-effecting call.
41. As the commercial product, I want retries for timeout, connect failure, 429 and 5xx, with backoff and a hard attempt cap, so that transient provider faults do not fail the first blip.
42. As the commercial product, I want 401, 403, contract mismatch and invalid query not to retry, so that permanent errors fail fast.
43. As the commercial product, I want httpx transport retries left at zero, so that application-level retry policy stays visible and testable like the OpenRouter adapter.
44. As a developer, I want a deterministic in-repo fake search base, so that CI does not need OpenSearch or the real CombineDatabase.
45. As a developer, I want the fake provider to expose seeded people, publications, current absence, auth failure, version mismatch, timeout and 5xx scenarios, so that every stable error path can be driven without sleeps against production timeouts.
46. As a developer, I want contract tests to exercise the real adapter against the fake provider, so that tests do not bypass consumer parsing the way raw HTTP to a mock would.
47. As a developer, I want the fake provider responses to validate against the same contract models the adapter uses, so that consumer and fake cannot drift.
48. As a developer, I want Compose to run the fake search base as a service, so that API and worker containers in local and CI use the same RN_SEARCH_BASE_BASE_URL pattern as OpenRouter.
49. As a developer, I want unit tests to run without Docker by talking to the fake app in-process, so that `pytest -m "not integration"` stays fast.
50. As a future CombineDatabase implementer, I want the contract version, error categories and payload shapes documented in this product, so that the real provider can satisfy the same consumer tests later.
51. As the commercial product, I want no tenant-facing HTTP routes in this slice, so that recruiters do not see an unfinished search UI before local talent identity exists.
52. As the commercial product, I want no OpenSearch DSL constructed in business modules, so that the search-base boundary stays the only retrieval seam.
53. As the commercial product, I want natural-language expert search on the current search base to remain unused, so that two LLM interpreters cannot disagree with a confirmed job requirement version.
54. As the commercial product, I want matching algorithm weights kept out of this contract, so that an immutable algorithm version in this product can score hits later.
55. As a tenant, I want this slice to consume no search, match, report or contact-unlock quota, so that building the client does not bill anyone.
56. As a platform operator, I want secrets for the search base injected only via RN_ environment variables, so that credentials are not committed.
57. As the commercial product, I want batch size capped at 500 canonical person IDs, so that a caller cannot request unbounded hydration.
58. As the commercial product, I want detail and evidence of a currently absent ID to return current absence rather than an empty person, so that missing and found are not conflated.
59. As the commercial product, I want malformed JSON or missing required response fields to be adapter errors, so that a partial provider payload cannot be treated as a valid hit.
60. As the commercial product, I want Chinese-identity values treated as inferred search-base classifications, so that the contract does not present them as nationality or ethnicity facts.

## Implementation Decisions

- This repository implements only the consumer side. The real search base (currently CombineDatabase / OpenSearch) is not deployed here and is not queried via DSL.
- Follow ADR 0025 and the glossary terms 检索底座, 规范人物, 数据版本, 检索命中, 人物证据, 当前缺失, 检索契约版本.
- Add a search-base adapter in the same style as the OpenRouter adapter: typed client config, async httpx client, explicit error categories with retryable flags, injectable client for tests.
- Configuration uses existing Pydantic Settings `RN_` prefix and `extra=ignore`. New settings: search-base base URL, service API key as `SecretStr`, request timeout seconds (default 10, allowed 3–30), search-contract version identifier (frozen default for v1). Do not scatter `os.environ`.
- Search-contract version v1 declares it can execute job-requirement Schema v1 and Schema v2 because they share the same executable field catalog. A future schema that adds search-base fields requires a new search-contract version.
- HTTP calls send service authentication, search-contract version, and a client-generated request ID. Successful responses must echo the request ID and include the current data version. Adapter rejects responses that omit them.
- Capabilities: health; talent search; person detail; batch person read; person evidence. No natural-language endpoint, no contact reveal, no score/weights, no historical data-version query parameter.
- Talent search request body: hard conditions (list, may be empty) plus a required non-empty research topic query, plus a hit limit (1–500, default 500). Preference conditions, unsupported conditions, job text and user utterances are not sent. Adapter raises before HTTP if a caller passes them.
- Hard-condition fields and operators are exactly Schema v1: `qs_top200_rank` / `world_top500_rank` / `h_index` / `total_citations` with `gte`/`lte`/`between`; `chinese_identity` / `country` with `eq`/`in`; `current_affiliation` with `match`/`match_phrase`. Values for `chinese_identity` are 国内华人 / 海外华人 / 外国人. Flattened AND only; no OR/NOT trees.
- Search hit: canonical person ID, historical source IDs, current executable fields, optional has-contact marker, hit publication IDs, finite numeric semantic score. Hits in one response share one data version and are ordered by semantic score descending. No email, phone or other full contact values.
- Current executable fields on hits and details: display name, current affiliation, country, chinese identity, h-index, total citations, QS top-200 rank, world top-500 rank, plus the identity IDs above. Missing optional ranks may be null; identity and data version may not.
- Person evidence: publications (stable publication ID, title, year, venue, optional snippet) and structured-field provenance without contact claim values. Evidence is keyed by canonical person ID at the current data version, not by a search query.
- Batch read: up to 500 IDs. Success payload contains found persons and a list of currently absent IDs. HTTP success with current absence is not an error. Auth, timeout, 5xx and contract mismatch fail the whole batch.
- Detail or evidence for a single currently absent ID returns a typed current-absence outcome, not a synthesized empty person.
- Error categories (stable strings): `unauthenticated`, `forbidden`, `contract_version_incompatible`, `invalid_query`, `timeout`, `network_error`, `rate_limited`, `unavailable`, `invalid_response`. Current absence is not an error category.
- Retry policy lives in the adapter, not httpx `AsyncHTTPTransport(retries=…)`. Transport retries stay 0 (httpx default) because that mechanism only covers connect failures and would hide policy. All four data capabilities plus health are safe reads and may retry. Retryable: timeout, network error, 429, 5xx. Not retryable: 401, 403, contract mismatch, invalid query, invalid response. Maximum 3 attempts, exponential backoff, honor `Retry-After` when present (same parsing approach as OpenRouter).
- Timeouts use an explicit httpx timeout on the client/request (httpx default is 5s if unset). Search, detail, batch and evidence share `RN_SEARCH_BASE_TIMEOUT_SECONDS`.
- Do not add search base to `/health/ready` dependency names. Platform health stays postgres, redis and object storage. Adapter exposes `check_health()` for Compose/CI and later jobs; fake provider serves a liveness path for container healthchecks.
- In-repo fake search base mirrors fake OpenRouter: FastAPI app in the API package, Compose service, scenario switches for auth denial, version mismatch, timeout, 5xx, current absence, and a seeded current data version with a small deterministic person/publication set. Reset between tests. No real API keys.
- Shared Pydantic contract models are the source of truth for request/response shapes. Adapter parses into those models; fake provider serializes the same models. This is the consumer-driven contract without introducing a Pact broker.
- No database migration is required unless a future slice persists hits. This slice does not persist canonical persons, snapshots or usage ledger entries.
- No tenant routers, no frontend, no Playwright in this slice. Workers import the adapter; they do not enqueue matching yet.
- Logging, audit and notifications must not record full contact values (there should be none) or service API keys. Request IDs and data versions are safe to log.

## Testing Decisions

Tests assert externally observable adapter behavior: typed results, error categories, retryable flags, request headers actually sent, and that payloads never contain full contacts. They do not assert private helper structure, OpenSearch internals, or the real CombineDatabase.

Primary seam (one seam): the search-base adapter talking to the in-repo fake search base. Contract tests must call the real adapter (Pact consumer rule: do not bypass the client with raw HTTP). The fake app is the provider double, as fake OpenRouter already is for LLM calls.

- Unit tests (`pytest -m "not integration"`): in-process ASGI or equivalent against the fake app; cover search, detail, batch partial success, evidence, health, auth failure, contract mismatch, invalid query, timeout, 429/5xx retry exhaustion, non-retry of 401, header injection (auth, contract version, request ID), data version required, contact omission, preference-condition rejection before HTTP, research-topic required, hit limit bounds, batch cap, invalid/missing response fields.
- Fake-app tests: scenario switches and contract-model round-trip, same prior art as fake OpenRouter tests.
- Integration tests with the existing uvicorn-on-loopback pattern: adapter configured via settings like OpenRouter’s fake base URL fixture; at least one real HTTP round-trip for search and one for batch current absence.
- Compose: fake search-base service with healthcheck; API/worker receive `RN_SEARCH_BASE_*`; CI compose job already runs dependency probes and can add a client-side health check against the fake. Do not require a live CombineDatabase.
- No new frontend tests. No RBAC matrix on tenant routes (there are none). Isolation is: only service credentials are accepted by the fake; a missing/wrong key yields `unauthenticated`.
- Migration round-trip is N/A if no migration; if a settings-only change, do not add a no-op migration.
- Provider verification for the real search base is out of this repository’s CI. Keep the contract models and fake scenarios exportable so CombineDatabase can later verify it implements the same shapes.

## Out of Scope

- Implementing or deploying the real CombineDatabase / OpenSearch service in this repository.
- Natural-language expert search on the search base; commercial NL search (#14).
- Local talent IDs, alias mapping, field snapshots and 暂时不可用 (#13).
- Match runs, algorithm versions, 50/20/20/10 scoring, persisting 100 hits (#15).
- Tenant talent pool and job candidates (#16).
- Full contact read, unlock quota and exports (#17).
- Adding search base to platform health.
- Tenant or platform-admin HTTP APIs and UI for search.
- Usage ledger charges.
- Pact broker, Kafka, or any new test infrastructure beyond the fake-provider pattern.
- Historical data-version reads on the search base.
- Co-author graph and Neo4j (PRD out of scope).

## Further Notes

- Issue #2 is closed; this slice is unblocked. #13 remains blocked on this slice.
- CombineDatabase is the current implementation name of 检索底座; do not put that name in user-facing copy or `CONTEXT.md`.
- Schema v2 currently copies v1’s field catalog; search-contract v1 may execute both. If they diverge, stop and add a new search-contract version.
- Homepage degraded-health Playwright scenarios must keep working: do not expand `/health/ready` in this slice.
- When the real provider exists, point `RN_SEARCH_BASE_BASE_URL` at it; CI continues to use the fake, the same way OpenRouter live probes are not a CI gate.
