# Production Platform Roadmap (Internal Build First)

> **Status:** Active planning document  
> **Scope:** Production-grade Weave platform — ontology, graph, retrieval, data layer, quality  
> **Out of scope (for now):** Partner access, public HTTPS, ngrok, BYOK, multi-tenant SaaS deployment  
> **Last updated:** 2026-05-30

---

## 1. North star

An internal operator can:

1. Connect enterprise data → **Knowledge Fabric**
2. Auto-discover **ontology** (entities, relationships, attributes) with human approval
3. Materialize a **canonical knowledge graph** per fabric
4. **Retrieve and answer** using vector + graph context (not vector alone)
5. Rely on **versioning, audit, backup, and quality gates**
6. Operate under **enterprise governance** (SSO, RBAC, fabric ACLs) — Phase 6
7. Monitor knowledge quality via **Insights Studio** — Phase 7
8. Support **agent session memory** and feedback loops — Phases 8–9

Deployment and external partner APIs are added **after** this core is solid.

---

## 2. Current state vs production target

| Capability | Today | Production target |
|------------|--------|-------------------|
| Fabric ingest (DB, CSV, PDF) | Works | Job-based, idempotent, observable |
| Vector index | Chroma (local/volume) | Managed + backup; path to scale |
| Metadata | `fabrics.json`, scattered JSON | PostgreSQL (single source of truth) |
| Ontology discovery | Beta; rules-heavy; file persistence | Universal schema LLM + rules; DB; auto-linked to fabric |
| Knowledge graph | Heuristic co-occurrence (`knowledge_graph_service`) | Canonical graph from **approved ontology** |
| Graph storage | None (computed per request) | Durable graph store (see §5) |
| Graph in retrieval | Not used | Graph-augmented `/retrieve` and `/query` |
| Governance | Review UI exists | Approved-only serving; immutable versions; audit |
| Quality | Ad hoc manual testing | Golden eval suite in CI |
| Background jobs | Inline / threads | Queue + workers |
| Enterprise governance (SSO, RBAC) | API keys only | SSO + RBAC + fabric ACLs + expanded audit |
| Insights Studio | Context Analysis page only | Unified insights hub (fabric health, ontology quality, graph coverage) |
| Agent memory tiers | Not implemented | Session memory API; episodic feedback log (v2) |
| Lineage Explorer | Enrichment metadata only | Dedicated drill-down UI (evidence → source) |
| Cost optimization | Chunk caps in config only | Per-fabric token/cost tracking + budgets |
| Impact loops | Not implemented | Outcome metrics + feedback → enrichment pipeline |
| Personalized experiences | Not implemented | Persona-based views (light); full personalization deferred |

---

## 3. Phased roadmap (summary)

| Phase | Focus | Duration (estimate) | Priority |
|-------|--------|---------------------|----------|
| **Phase 1** | Data & fabric foundation | 8–10 weeks | P0 — core |
| **Phase 2** | Ontology production | 10–14 weeks | P0 — core |
| **Phase 3** | Canonical knowledge graph + storage | 8–12 weeks | P0 — core |
| **Phase 4** | Graph-augmented retrieval & Q&A | 8–10 weeks | P0 — core |
| **Phase 5** | Quality, observability, internal auth | Ongoing (start in Phase 1) | P0 — core |
| **Phase 6** | Enterprise governance & trust | 8–12 weeks | **P0 — build first** (enterprise gate) |
| **Phase 7** | Insights Studio & operational intelligence | 6–10 weeks | **P1 — build second** |
| **Phase 8** | Agent memory tiers | 6–8 weeks | **P1 — build third** (if agents are primary consumption) |
| **Phase 9** | Impact loops & personalization | 8–12 weeks | **P2 — build last** |

Phases 2–3 depend on Phase 1 metadata store. Phase 5 eval harness should start as soon as a stable CSNP fabric exists.

**Enterprise expansion priority (post core P1–P5):** Phase 6 → Phase 7 → Phase 8 → Phase 9. Do not start Phase 9 before golden evals and usage telemetry exist (Phase 5 + Phase 7).

### Architecture diagram alignment

Reference: Weave Knowledge Fabric vision diagram (Data & Foundations → Retrieval Memory → Knowledge Patterns → Governance & Trust → Impact Frontier).

| Diagram layer | Phases that deliver it |
|---------------|------------------------|
| Data & Foundations | Phase 1 (mostly shipped / in progress) |
| Retrieval Memory (vector + graph) | Phases 3–4 (hybrid at query time) |
| Retrieval Memory (short/long/episodic) | Phase 8 |
| Knowledge Patterns (core) | Phases 2–4 |
| Knowledge Patterns (Insights Studio) | Phase 7 |
| Governance & Trust (full) | Phase 6 (+ lineage/cost in Phase 7) |
| Impact Frontier | Phase 9 |

Items explicitly **not** in scope as standalone platforms: general-purpose episodic memory SaaS, enterprise FinOps suite, BI competitor to Tableau/Looker.

---

## Phase 1 — Data & fabric foundation

**Goal:** Fabrics and platform metadata are durable, job-driven, and restorable.

### Action items

| ID | Action item | Details | Priority |
|----|-------------|---------|----------|
| P1-01 | **Introduce PostgreSQL for platform metadata** | Fabrics, connector config, training status, job runs, API config (future). Replace or migrate from `backend/data/fabrics.json`. | P0 |
| P1-02 | **SQLAlchemy models + migrations** | Alembic migrations; versioned schema. Tables: `fabrics`, `fabric_jobs`, `fabric_connectors`, `fabric_stats`. | P0 |
| P1-03 | **Dual-write / migration script** | One-time migration from JSON → Postgres; keep read fallback during transition. | P0 |
| P1-04 | **Async fabric lifecycle jobs** | Queue (Celery, RQ, or ARQ) + worker process: `ingest → chunk → embed → index → train`. | P0 |
| P1-05 | **Job state machine** | States: `queued`, `running`, `indexing`, `training`, `ready`, `failed`. Persist progress % and error payload. | P0 |
| P1-06 | **UI job progress** | Surface job status on fabric list/detail (replace opaque “training” only). | P1 |
| P1-07 | **Idempotent fabric rebuild** | Same source + config → safe re-run without duplicate corrupt state. | P0 |
| P1-08 | **Standardize row → chunk format** | Unified chunk schema across Databricks, Snowflake, CSV (metadata: table, row, columns). | P1 |
| P1-09 | **Chroma backup strategy** | Document + script: snapshot `chroma_db/` with DB metadata; restore procedure. | P0 |
| P1-10 | **Uploads & models path policy** | Centralize paths via `settings.*`; prod env vars only (already started in `config.py`). | P1 |
| P1-11 | **Connector validation hardening** | Pre-flight checks before job enqueue; clear error messages in UI. | P1 |
| P1-12 | **Incremental refresh design** | Design doc for delta ingest (implement full refresh first, delta in Phase 2+). | P2 |

### Exit criteria (Phase 1)

- [ ] Create 10 fabrics; restart stack; all metadata intact without manual migration
- [ ] Failed ingest surfaces actionable error in UI and DB
- [ ] Backup + restore tested on clean machine
- [ ] No production dependency on hand-editing JSON files

---

## Phase 2 — Ontology production

**Goal:** Ontology is automatic, reviewable, DB-backed, and **linked to every fabric**.

Reference: `docs/ENHANCEMENT_UNIVERSAL_SCHEMA_UNDERSTANDING.md`

### Action items

| ID | Action item | Details | Priority |
|----|-------------|---------|----------|
| P2-01 | **Schema-aware LLM analysis (Layer 1)** | New pipeline step: input = table name, column list, types, 5–20 sample rows, tags. Output = proposed entities, relationships, PKs, FKs, attributes. Primary signal; rules become secondary. | P0 |
| P2-02 | **Refactor `discovery_orchestrator`** | Order: LLM schema pass → rules (`concept_extractor`) → merge → inference → assemble. | P0 |
| P2-03 | **Tabular fabric → ontology input** | On DB/CSV fabric create, build schema profile from ingested metadata (not random text chunks only). | P0 |
| P2-04 | **Auto-trigger discovery on fabric ready** | Fabric job `ready` → enqueue ontology discovery for linked project. | P0 |
| P2-05 | **Fabric ↔ ontology linkage** | DB columns: `fabrics.ontology_project_id`, `fabrics.approved_ontology_version_id`. | P0 |
| P2-06 | **Ontology persistence in PostgreSQL** | Migrate from file-only `ontology_data/` for projects, versions, classes, relationships, attributes, evidence, discovery runs. | P0 |
| P2-07 | **Keep JSON export** | `OntologyExportService` remains for portability; DB is source of truth. | P1 |
| P2-08 | **Approval workflow (production rules)** | Only `approved` versions eligible for graph build and retrieval. Draft edits → new version. | P0 |
| P2-09 | **Immutable approved versions** | Approved snapshot frozen; changes require new version + re-approve. | P0 |
| P2-10 | **Audit log** | Who approved/rejected/edited; timestamp; version id. | P1 |
| P2-11 | **Pre-approve validation gates** | Extend `ontology_validator`: orphan classes, dangling relationships, missing evidence, duplicate normalized names. Block approve on critical failures. | P0 |
| P2-12 | **Evidence requirements** | Every relationship must cite source (table/column/chunk/snippet). UI surfaces evidence on hover. | P1 |
| P2-13 | **Human edit → feedback loop (v1)** | Log overrides; design hook for few-shot prompts in future (full loop deferred). | P2 |
| P2-14 | **Statistical schema signals (Layer 2)** | Uniqueness ratios, null rates, regex patterns (email, MRN, ICD) to boost FK/PK inference. | P1 |
| P2-15 | **Domain packs (Layer 3, optional)** | Pluggable rule packs (healthcare, ITSM) as boosters only — not primary logic. | P2 |

### Exit criteria (Phase 2)

- [ ] New Databricks/CSV schema → entities **and** relationships without new Python rules
- [ ] Analyst can approve ontology; approved version locked
- [ ] Every production fabric has linked ontology project + approved version (or explicit waiver flag)
- [ ] Ontology survives restart; no file-only dependency for serving path

---

## Phase 3 — Canonical knowledge graph & graph storage

**Goal:** One durable, queryable graph per fabric — built from **approved ontology**, not text co-occurrence.

### Graph storage decision (recommended path)

| Option | Recommendation | Notes |
|--------|----------------|-------|
| **PostgreSQL (property graph tables)** | **Start here (v1)** | Same ops stack as metadata; adjacency list or JSONB edges; good for 10³–10⁶ nodes per fabric |
| **Neo4j** | **v2 if traversal-heavy** | Native Cypher, graph algorithms; extra service to operate |
| **Amazon Neptune / managed** | Deploy phase | When cloud deployment starts |

**v1 recommendation:** PostgreSQL graph tables + application-layer traversal (1–2 hops). Migrate to Neo4j only if profiling shows need.

### Graph data model (canonical)

```
Node
  - id, fabric_id, ontology_class_id
  - label, normalized_name
  - properties (JSONB)
  - source_table, source_column (optional)
  - ontology_version_id
  - created_at

Edge
  - id, fabric_id
  - source_node_id, target_node_id
  - relationship_type (from ontology)
  - properties (JSONB)
  - confidence, evidence_refs (JSONB)
  - ontology_version_id

GraphBuildRun
  - fabric_id, ontology_version_id, status, node_count, edge_count, built_at
```

Instance-level nodes (e.g. `Member M000375`) can be Phase 3b; **schema-level graph first** (MemberDim → Diagnosis → ClaimFact).

### Action items

| ID | Action item | Details | Priority |
|----|-------------|---------|----------|
| P3-01 | **Graph schema DDL** | Postgres tables: `graph_nodes`, `graph_edges`, `graph_build_runs` (+ indexes on `fabric_id`, relationship type). | P0 |
| P3-02 | **Graph materialization service** | `GraphMaterializationService`: approved ontology version → nodes/edges. Map classes → nodes; relationships → edges. | P0 |
| P3-03 | **Graph build job** | Trigger on ontology approve (or fabric ready + approved ontology). Async job with status in UI. | P0 |
| P3-04 | **Replace heuristic graph for serving** | `GET /knowledge/{id}/knowledge-graph` reads **canonical graph** from DB, not `knowledge_graph_service.build_graph()`. | P0 |
| P3-05 | **Deprecate or relabel heuristic graph** | Move co-occurrence builder to `exploratory_graph` endpoint or remove from UI to avoid confusion. | P1 |
| P3-06 | **Graph API: traversal** | Internal API: `get_neighbors(fabric_id, node_id, hops=1)`, `get_subgraph(fabric_id, entity_types[])`. | P0 |
| P3-07 | **Sync with ontology export** | `OntologyExportService.export_graph()` writes same model as DB graph (consistency check). | P1 |
| P3-08 | **ServiceNow structured path** | Keep `_build_structured_servicenow_graph` as input to materializer, not parallel code path. | P1 |
| P3-09 | **Graph versioning** | Graph tagged with `ontology_version_id`; rebuild on new approval; keep previous version read-only. | P0 |
| P3-10 | **Graph validation** | Orphan nodes, duplicate edges, circular ref warnings before mark `ready`. | P1 |
| P3-11 | **UI: canonical graph view** | `FabricKnowledgeGraph.tsx` shows schema graph + stats from DB; entity/relationship types from ontology labels. | P0 |
| P3-12 | **Instance graph (optional v2)** | Materialize row-level nodes from chunks where IDs exist (MemberDim keys) — higher volume, do after schema graph stable. | P2 |

### Exit criteria (Phase 3)

- [ ] CSNP fabric graph shows typed entities (Member, Diagnosis, Claim, …) and FK-style edges from schema
- [ ] Graph persists across restart; rebuild is a job, not on every GET
- [ ] UI and API expose one graph story (canonical only)
- [ ] Graph build tied to approved ontology version

---

## Phase 4 — Graph-augmented retrieval & Q&A

**Goal:** `/retrieve` and `/query` use **vector + graph + ontology context** by default.

### Retrieval pipeline (target)

```
User question
  → [1] Vector search (Chroma top-k)
  → [2] Entity linking (question → graph node types / instances)
  → [3] Graph expansion (1–2 hops on canonical graph)
  → [4] Structured filters (tabular: column-aware filters when question implies aggregation/ranking)
  → [5] Context merge & rank
  → [6] LLM synthesis (internal key) with ontology-aware system prompt
  → Response: { answer, chunks, graph_paths, entities, ontology_version, confidence }
```

### Action items

| ID | Action item | Details | Priority |
|----|-------------|---------|----------|
| P4-01 | **`RetrievalOrchestrator` service** | Single entry for retrieve/query; composes vector + graph + optional structured steps. | P0 |
| P4-02 | **Entity linking step** | Map query terms to ontology classes / graph nodes (embedding or keyword + ontology labels). | P0 |
| P4-03 | **Graph expansion step** | From linked nodes, fetch 1–2 hop neighbors; attach related chunks if instance data exists. | P0 |
| P4-04 | **Context merge & dedupe** | Rank merged chunks + graph path summaries; token budget for LLM. | P0 |
| P4-05 | **Ontology-aware query prompt** | Inject approved entity/relationship summary for fabric domain into `/query` system context. | P0 |
| P4-06 | **Structured tabular queries (v1)** | Detect patterns (“highest BenefitCost”, “top 10”, “count by plan”); apply metadata filters on chunks or optional warehouse pushdown design. | P1 |
| P4-07 | **Standard response envelope** | Extend API: `chunks`, `graph_context`, `entities`, `ontology_version_id`, `retrieval_trace` (debug). | P0 |
| P4-08 | **Feature flag** | `USE_GRAPH_RETRIEVAL=true` for gradual rollout per fabric. | P1 |
| P4-09 | **Fallback behavior** | If no graph for fabric, fall back to vector-only (log warning). | P0 |
| P4-10 | **Update internal UI** | Test LLM, Context Analysis, Agent Utilities use new orchestrator. | P1 |
| P4-11 | **Remove duplicate retrieval paths** | Consolidate ad hoc fetch logic in frontend where possible; use `utils/api.ts`. | P2 |

### Exit criteria (Phase 4)

- [ ] Golden CSNP questions improve vs vector-only baseline (see Phase 5 metrics)
- [ ] Response includes traceable graph/ontology version
- [ ] “Diabetic + highest cost” class of questions materially better than embedding-only retrieve

---

## Phase 5 — Quality, observability & internal platform ops

**Goal:** Ship with confidence; diagnose failures without guesswork.

### Action items

| ID | Action item | Details | Priority |
|----|-------------|---------|----------|
| P5-01 | **Golden eval dataset — CSNP** | 15–25 questions + expected signals (member IDs, tables, conditions, cost ordering). JSON in `backend/tests/golden/csnp/`. | P0 |
| P5-02 | **Golden eval — ITSM** | Same for incident fabric. | P1 |
| P5-03 | **Eval runner CLI / pytest** | Score retrieval grounding, entity recall, optional LLM judge. Fail CI below threshold. | P0 |
| P5-04 | **Structured logging** | `fabric_id`, `ontology_version_id`, `job_id`, retrieval stages, latency on every request. | P0 |
| P5-05 | **Metrics** | Prometheus-style or simple stats: retrieve p95, job failure rate, graph build duration, index size. | P1 |
| P5-06 | **Health endpoints** | Extend `/health`: DB connectivity, Chroma reachable, queue worker alive. | P0 |
| P5-07 | **Internal auth (UI)** | Login + roles: admin, analyst, viewer. Fabric-scoped permissions. | P1 |
| P5-08 | **Secrets management** | No secrets in repo; `.env` for dev only; prod via env/vault. | P0 |
| P5-09 | **Runbooks** | Fabric failed job, ontology reject loop, graph rebuild, backup restore. | P1 |
| P5-10 | **Release gate** | No merge to main if golden eval regression > agreed delta. | P0 |

### Exit criteria (Phase 5)

- [ ] CI runs golden eval on PR touching retrieval/ontology/graph
- [ ] On-call can trace a bad answer to vector vs graph vs ontology version
- [ ] Health check fails if DB or Chroma down

---

## Phase 6 — Enterprise governance & trust (build first)

**Goal:** Pass enterprise security review and production governance requirements. This phase is the adoption gate for external deployments.

**Prerequisite:** Phases 1–5 core stable (Postgres metadata, approved ontology, canonical graph, retrieval orchestrator).

### Action items

| ID | Action item | Details | Priority |
|----|-------------|---------|----------|
| P6-01 | **SSO integration (OIDC/SAML)** | Login for UI via WorkOS, Auth0, or Keycloak. Map IdP groups → platform roles. | P0 |
| P6-02 | **RBAC — three roles minimum** | `admin`, `analyst`, `viewer`. Role enforced on API and UI routes. | P0 |
| P6-03 | **Fabric-level ACLs** | `fabric_permissions` table: user/role → fabric read/write/admin. Filter list/query/retrieve by permission. | P0 |
| P6-04 | **Approved-only serving** | `/retrieve` and `/query` refuse fabrics without `approved_ontology_version_id` when `REQUIRE_APPROVED_ONTOLOGY=true`. | P0 |
| P6-05 | **Expanded audit log** | Log: fabric create/delete, ontology approve/reject, graph build/export, query/retrieve (fabric_id, user, timestamp). | P0 |
| P6-06 | **Query/retrieve audit trail** | Append-only `access_audit_logs` for compliance; configurable retention. | P1 |
| P6-07 | **Secrets vault for connectors** | Encrypt `connection_info` credentials; reference vault keys instead of plaintext in DB. | P1 |
| P6-08 | **Policy enforcement hardening** | Extend `/agent/policy/evaluate` and fabric guardrails to all query paths consistently. | P1 |
| P6-09 | **Security runbook** | Key rotation, SSO outage, ACL misconfiguration, audit export procedure. | P1 |

### Exit criteria (Phase 6)

- [ ] SSO login works; local dev bypass documented
- [ ] Viewer cannot approve ontology or trigger graph build
- [ ] User sees only fabrics they are permitted to access
- [ ] Unapproved fabrics blocked from production retrieval (when flag on)
- [ ] Security reviewer can export 30-day audit trail

---

## Phase 7 — Insights Studio & operational intelligence (build second)

**Goal:** Productize existing analytics into a unified Insights hub — not a separate BI tool. Answers: “Is our knowledge fabric trustworthy and complete?”

**Prerequisite:** Phase 6 RBAC (insights scoped per fabric/role).

### Insights Studio v1 scope (in scope)

| View | Source / build from |
|------|---------------------|
| Fabric health | Job history, chunk count, index status, last ingest |
| Ontology quality | Approval rate, evidence coverage, trust score, validation warnings |
| Graph coverage | Node/edge counts, orphan entities, relationship gaps |
| Retrieval quality | Golden eval scores, grounding trends |
| Context analysis | Extend existing `/context` page into Insights Studio tab |

### Out of scope (do not build)

- Custom dashboard builder
- Competing with Tableau / Looker / Power BI
- Revenue/ops KPI dashboards unrelated to knowledge quality

### Action items

| ID | Action item | Details | Priority |
|----|-------------|---------|----------|
| P7-01 | **Insights Studio shell** | New route `/insights` with fabric selector and tabbed views. Rebrand Context Analysis as one tab. | P0 |
| P7-02 | **Fabric health panel** | Jobs, index size, last discovery/graph build, failure rate. | P0 |
| P7-03 | **Ontology quality panel** | Evidence %, unapproved elements, trust score, validator failures. | P0 |
| P7-04 | **Graph coverage panel** | Orphan nodes, duplicate edges, version history, rebuild status. | P0 |
| P7-05 | **Retrieval quality panel** | Surface golden eval results per fabric; trend over time. | P1 |
| P7-06 | **Lineage Explorer v1** | Drill-down UI: ontology element / graph edge → `OntologyEvidence` → source table, column, chunk, document span. | P0 |
| P7-07 | **Lineage API** | `GET /api/v1/ontology/lineage/{element_id}` and graph edge lineage endpoint. | P1 |
| P7-08 | **Cost tracking v1** | Log LLM tokens per `/query` and discovery job; aggregate per fabric/day. | P1 |
| P7-09 | **Cost budgets** | Configurable `max_llm_tokens_per_fabric_per_day`; soft warn + hard block option. | P2 |
| P7-10 | **Insights export** | PDF/CSV summary for analyst sign-off packages. | P2 |

### Exit criteria (Phase 7)

- [ ] Operator opens Insights Studio and sees health + ontology + graph + retrieval tabs for a fabric
- [ ] Lineage Explorer traces at least one relationship to source column or document chunk
- [ ] Token usage visible per fabric for last 7 days
- [ ] Golden eval scores displayed (depends on P5-01, P5-03)

---

## Phase 8 — Agent memory tiers (build third)

**Goal:** Support multi-turn agent consumption of Weave retrieval without building a general-purpose memory platform.

**Prerequisite:** Phase 6 auth (sessions tied to user); Phase 4 retrieve API stable.

### Weave mapping of memory tiers

| Diagram term | Weave implementation | Phase |
|--------------|----------------------|-------|
| Long-term memory | Fabric + vector index + canonical graph | Phases 1–4 (exists) |
| Short-term memory | Agent session store (conversation turns) | Phase 8 |
| Episodic memory | Query log + user corrections → enrichment queue | Phase 8 (v1 log), Phase 9 (closed loop) |

### Action items

| ID | Action item | Details | Priority |
|----|-------------|---------|----------|
| P8-01 | **Agent session model** | Tables: `agent_sessions`, `agent_session_turns` (role, content, fabric_id, ontology_version_id). | P0 |
| P8-02 | **Session memory API** | `POST /api/v1/agent/sessions`, append turn, `GET` last N turns for context assembly. | P0 |
| P8-03 | **Retrieve with session context** | Optional `session_id` on `/retrieve` — prepend recent turns to entity linking / query expansion. | P1 |
| P8-04 | **Session TTL and limits** | Configurable expiry; max turns per session; per-user session cap. | P1 |
| P8-05 | **Feedback capture** | `POST /api/v1/agent/feedback` — thumbs up/down, correction text, linked retrieve response id. | P0 |
| P8-06 | **Episodic log** | Append-only `retrieval_episodes` — query, chunks returned, graph paths, feedback flag. | P1 |
| P8-07 | **Corrections → enrichment queue** | Negative feedback creates enrichment candidate (feeds P2-13 / ontology enrichment). | P1 |
| P8-08 | **Partner session docs** | Document BYOK + session pattern for external agents in partner guide. | P1 |

### Out of scope (defer or integrate later)

- Full episodic memory platform (Mem0/Zep-class)
- Cross-fabric agent memory
- Autonomous agent orchestration

### Exit criteria (Phase 8)

- [ ] Agent completes 5-turn conversation on one fabric with session context in retrieve
- [ ] User submits correction; enrichment candidate appears in queue
- [ ] Session expires per TTL; audit shows session ownership

---

## Phase 9 — Impact loops & personalization (build last)

**Goal:** Measure outcomes and close the loop from usage → improvement. Light personalization only — not a recommendation engine.

**Prerequisite:** Phase 7 Insights Studio + Phase 8 feedback capture + Phase 5 golden evals with baseline data.

### Action items

| ID | Action item | Details | Priority |
|----|-------------|---------|----------|
| P9-01 | **Outcome tagging** | Optional `outcome` field on feedback (resolved, escalated, incorrect, helpful). | P1 |
| P9-02 | **Fabric impact metrics** | Queries/week, feedback rate, golden eval trend, time-to-answer proxy. | P1 |
| P9-03 | **Impact loop v1** | Monthly report: low-scoring retrieval patterns → suggested ontology enrichment targets. | P1 |
| P9-04 | **Closed feedback loop** | Approved enrichment from retrieval feedback updates ontology version → graph rebuild job. | P2 |
| P9-05 | **Capture loop completion** | Human edit + retrieval feedback both feed discovery/enrichment (closes diagram Capture Loop). | P2 |
| P9-06 | **Persona views (light)** | `executive` vs `analyst` Insights Studio layouts — template switch, not ML personalization. | P2 |
| P9-07 | **Role-based default fabrics** | Landing dashboard shows fabrics relevant to RBAC role. | P2 |
| P9-08 | **Business outcome hooks** | Optional external webhook when golden eval regression or impact threshold crossed. | P2 |

### Out of scope (defer indefinitely)

- Netflix-style personalization / per-user ranking models
- Enterprise FinOps suite beyond Phase 7 token budgets
- Multi-tenant partner marketplace

### Exit criteria (Phase 9)

- [ ] Impact report generated for one fabric over 30 days
- [ ] At least one retrieval feedback item resulted in approved ontology enrichment
- [ ] Executive vs analyst view available in Insights Studio

---

## 4. Cross-cutting implementation checklist

Use this as a master backlog (copy to issue tracker).

### Data layer
- [ ] P1-01 PostgreSQL metadata store
- [ ] P1-02 Alembic migrations
- [ ] P1-03 JSON → Postgres migration
- [ ] P2-06 Ontology in Postgres
- [ ] P1-09 Chroma backup/restore

### Jobs & async
- [ ] P1-04 Job queue + workers
- [ ] P1-05 Fabric job state machine
- [ ] P3-03 Graph build job
- [ ] P2-04 Auto ontology on fabric ready

### Ontology
- [ ] P2-01 Schema-aware LLM (Layer 1)
- [ ] P2-02 Orchestrator refactor
- [ ] P2-08 Approval workflow
- [ ] P2-11 Validation gates
- [ ] P2-05 Fabric ↔ ontology linkage

### Graph storage & serving
- [ ] P3-01 Graph DDL (Postgres v1)
- [ ] P3-02 Graph materialization service
- [ ] P3-04 Canonical graph API (replace heuristic)
- [ ] P3-06 Traversal API
- [ ] P3-09 Graph versioning
- [ ] P3-11 UI canonical graph

### Retrieval
- [ ] P4-01 RetrievalOrchestrator
- [ ] P4-02 Entity linking
- [ ] P4-03 Graph expansion
- [ ] P4-05 Ontology-aware prompts
- [ ] P4-07 Standard response envelope
- [ ] P4-06 Structured tabular queries (v1)

### Quality & ops
- [ ] P5-01 CSNP golden eval
- [ ] P5-03 Eval in CI
- [ ] P5-04 Structured logging
- [ ] P5-06 Extended health checks

### Enterprise governance (Phase 6 — priority 1)
- [ ] P6-01 SSO (OIDC/SAML)
- [ ] P6-02 RBAC (admin / analyst / viewer)
- [ ] P6-03 Fabric-level ACLs
- [ ] P6-04 Approved-only serving flag
- [ ] P6-05 Expanded audit log

### Insights Studio & lineage (Phase 7 — priority 2)
- [ ] P7-01 Insights Studio shell (`/insights`)
- [ ] P7-02 Fabric health panel
- [ ] P7-03 Ontology quality panel
- [ ] P7-04 Graph coverage panel
- [ ] P7-06 Lineage Explorer v1
- [ ] P7-08 Cost tracking v1

### Agent memory (Phase 8 — priority 3)
- [ ] P8-01 Agent session model
- [ ] P8-02 Session memory API
- [ ] P8-05 Feedback capture
- [ ] P8-06 Episodic retrieval log

### Impact & personalization (Phase 9 — priority 4)
- [ ] P9-01 Outcome tagging
- [ ] P9-02 Fabric impact metrics
- [ ] P9-03 Impact loop v1
- [ ] P9-05 Capture loop completion
- [ ] P9-06 Persona views (light)

---

## 5. Recommended first sprint (4–6 weeks)

Start here — smallest spine for everything else:

1. **P1-01 + P1-02** — Postgres + models for `fabrics` and `fabric_jobs`
2. **P1-04 + P1-05** — Job queue; move fabric indexing off request thread
3. **P2-05 + P2-04** — Link fabric to ontology project; auto-enqueue discovery
4. **P2-01** — Schema-aware LLM pass (MVP: column list + 10 sample rows)
5. **P5-01** — CSNP golden eval file (10 questions) — baseline **before** graph work
6. **P3-01 + P3-02** — Graph tables + materialize from approved ontology (schema-level only)

### Recommended sprint after core (Phases 6–7 entry)

Start enterprise expansion only after Phase 5 exit criteria are met:

1. **P6-01 + P6-02** — SSO + RBAC (three roles)
2. **P6-03** — Fabric ACLs
3. **P6-04 + P6-05** — Approved-only serving + expanded audit
4. **P7-01 + P7-06** — Insights Studio shell + Lineage Explorer v1
5. **P7-08** — Per-fabric token/cost tracking

---

## 6. Definition of done — production-grade platform (internal)

Ready to plan **deployment and partner access** when all are true:

- [ ] New schema → usable ontology without developer rule changes (P2-01 live)
- [ ] Every fabric has approved ontology + materialized graph (or explicit waiver)
- [ ] `/query` uses vector + graph context by default (P4-01)
- [ ] Metadata, ontology, graph in Postgres with tested backup/restore
- [ ] Fabric lifecycle is job-based with clear failure states
- [ ] Golden eval passes on release; regressions block merge
- [ ] Single graph story in UI/API (canonical, not heuristic)

### Definition of done — enterprise vision (Phases 6–9)

Ready to claim full **Weave Knowledge Fabric** vision (architecture diagram) when all are true:

- [ ] SSO + RBAC + fabric ACLs enforced (Phase 6)
- [ ] Approved-only serving available for production fabrics (Phase 6)
- [ ] Insights Studio shows health, ontology quality, graph coverage, retrieval scores (Phase 7)
- [ ] Lineage Explorer traces evidence to source (Phase 7)
- [ ] Per-fabric LLM token/cost tracking with budgets (Phase 7)
- [ ] Agent session memory API used by at least one partner integration (Phase 8)
- [ ] Retrieval feedback flows to enrichment queue (Phase 8)
- [ ] Impact report + one closed feedback → ontology improvement loop (Phase 9)

---

## 7. Explicitly deferred (post-platform)

| Item | When |
|------|------|
| Public HTTPS / ngrok / Cloudflare Tunnel | After internal prod stable |
| Partner API keys, BYOK, rate limits | After deployment architecture |
| Multi-tenant SaaS isolation | After Phase 6 auth + DB model proven |
| Neo4j / Neptune migration | If Postgres traversal insufficient (profile first) |
| Full agentic orchestration | Partners/agents consume your retrieval API later |
| Vercel / serverless backend | Not applicable to this backend shape |
| General-purpose episodic memory platform (Mem0/Zep-class) | Integrate if needed; do not build |
| Enterprise FinOps suite (beyond per-fabric token budgets) | After multi-tenant scale |
| BI platform / custom dashboard builder | Out of scope — Insights Studio is knowledge-quality only |
| Full ML personalization engine | Defer indefinitely; persona templates only (P9-06) |

---

## 8. Related documents

| Document | Purpose |
|----------|---------|
| `docs/ENHANCEMENT_UNIVERSAL_SCHEMA_UNDERSTANDING.md` | Layer 1–3 ontology architecture (P2-01…) |
| `docs/WEAVE_POSITIONING.md` | Product story once P3–P4 complete |
| `docs/WEAVE_PRESENTATION_PROMPTS.md` | 10-slide deck; align claims to phase completion |
| `docs/tech-stack/README.md` | Technical architecture reference |
| `docs/OUR_SOLUTION_VS_KNOWLEDGE_GRAPH.md` | KG vs ontology positioning |
| `backend/docs/ONTOLOGY_MODULE_README.md` | Current ontology module layout |
| `docs/ENHANCEMENT_HTTPS_EXTERNAL_ACCESS.md` | **Deferred** — partner/deploy phase |

---

## 9. Ownership template (fill in)

| Phase | DRI | Target start | Target complete |
|-------|-----|--------------|-----------------|
| Phase 1 — Data & fabric | TBD | | |
| Phase 2 — Ontology | TBD | | |
| Phase 3 — Graph storage | TBD | | |
| Phase 4 — Graph retrieval | TBD | | |
| Phase 5 — Quality & ops | TBD | | |
| Phase 6 — Enterprise governance | TBD | After P1–P5 core | |
| Phase 7 — Insights Studio | TBD | After P6 SSO/RBAC | |
| Phase 8 — Agent memory | TBD | After P6 + P4 retrieve stable | |
| Phase 9 — Impact & personalization | TBD | After P7 + P8 + golden eval baseline | |

---

*This document is the single source of truth for internal production build priorities. Update checkboxes and dates as items ship.*
