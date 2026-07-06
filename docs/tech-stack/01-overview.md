# Weave Platform — Overview

## 1. Executive Technical Summary

Weave is a hybrid retrieval intelligence platform designed for enterprise data domains where schema complexity, entity relationships, and governance requirements exceed the capability of vector-only retrieval systems.

The platform provides:

1. Knowledge Fabric lifecycle — ingest, chunk, embed, index, and serve content from heterogeneous sources.
2. Ontology discovery — automatic extraction of entities, attributes, and relationships with human approval workflows.
3. Canonical knowledge graph materialization — durable schema-level graphs derived from approved ontologies.
4. Graph-augmented retrieval — combined vector, ontology, and graph context for query and retrieve APIs.
5. Enterprise export — optional synchronization to Neo4j and Stardog/RDF for downstream graph analytics.

Weave is not a replacement for warehouse platforms, graph databases, or LLM providers. It is the control plane and semantic factory that sits above them.

---

## 2. Design Principles

| Principle | Description |
|-----------|-------------|
| Source agnostic | Connectors abstract Databricks, Snowflake, relational databases, documents, and application exports behind a unified fabric model. |
| Governance first | Ontology versions are reviewable, approvable, and immutable once approved; graph builds bind to approved versions. |
| Retrieval reliability | Vector search remains the primary recall mechanism; graph enrichment augments but does not replace embeddings. |
| Pluggable graph runtime | In-platform graph storage uses PostgreSQL; Neo4j and Stardog are certified export targets for enterprise consumption. |
| API-first | All operator and partner capabilities are exposed through versioned REST APIs. |
| Incremental enterprise maturity | Local development operates without external graph databases; production can enable Postgres, Neo4j, and Stardog progressively. |

---

## 3. Logical Architecture

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                         Presentation Tier                                │
│   React SPA · D3 Knowledge Graph · Ontology Studio · Fabric Console    │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │ HTTPS / REST
┌───────────────────────────────────▼─────────────────────────────────────┐
│                         Application Tier (FastAPI)                       │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────────────┐ │
│  │ Knowledge   │ │ Ontology     │ │ Platform     │ │ Graph           │ │
│  │ Fabric API  │ │ Discovery API│ │ Jobs API     │ │ Materialization │ │
│  └─────────────┘ └──────────────┘ └──────────────┘ └─────────────────┘ │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────────────┐ │
│  │ Retrieval   │ │ Training /   │ │ Search       │ │ Inbound API Key │ │
│  │ Orchestrator│ │ ML Models    │ │              │ │ Middleware      │ │
│  └─────────────┘ └──────────────┘ └──────────────┘ └─────────────────┘ │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────┐         ┌───────────────┐         ┌───────────────────┐
│ PostgreSQL    │         │ ChromaDB      │         │ File System       │
│ Metadata ·    │         │ Embeddings ·  │         │ Uploads · Models ·│
│ Ontology ·    │         │ Vector Index  │         │ Ontology artifacts│
│ Graph tables  │         │               │         │                   │
└───────────────┘         └───────────────┘         └───────────────────┘
        │                           │
        └───────────┬───────────────┘
                    ▼ (optional export)
        ┌───────────────────────┐
        │ Neo4j · Stardog (RDF) │
        └───────────────────────┘
                    ▲
        ┌───────────┴───────────┐
        │ Enterprise Sources    │
        │ Databricks · Snowflake│
        │ Postgres · MySQL · …  │
        └───────────────────────┘
```

---

## 4. Core Domain Objects

| Object | Definition |
|--------|------------|
| Knowledge Fabric | A bounded knowledge domain created from one or more sources; owns vector index partitions, metadata, optional ontology linkage, and graph builds. |
| Ontology Project | Workspace grouping source artifacts, discovery runs, and versioned ontology snapshots. |
| Ontology Version | Draft or approved snapshot of classes, relationships, attributes, constraints, and evidence. |
| Canonical Graph | Schema-level graph (entity types and relationship types) materialized from an approved ontology version. |
| Fabric Job | Asynchronous unit of work: ontology discovery, graph build, graph export, or ingest pipeline stages. |
| Chunk | Text segment stored in Chroma with metadata (source table, file, row, column context). |

---

## 5. Primary User Journeys (Technical)

### 5.1 Tabular enterprise source

```text
Connect source → Create fabric → Chunk + embed → Auto ontology discovery (schema LLM + rules)
→ Analyst approval → Graph materialization → D3 visualization + graph-augmented retrieve
→ Optional export to Neo4j / RDF / Stardog
```

### 5.2 Document source (PDF, DOCX, XML)

```text
Upload document → Create PDF fabric → Chunk + embed → Knowledge graph (exploratory or canonical)
→ Ontology discovery via fabric artifact bridge → Review → Approve → Canonical graph
```

### 5.3 Partner / agent consumption

```text
POST /retrieve/{fabric_id}  → chunks + graph context (no LLM on operator infrastructure)
POST /query/{fabric_id}     → LLM synthesis with BYOK option for external callers
```

---

## 6. Maturity Matrix

| Capability | Status |
|------------|--------|
| Multi-source fabric ingest | Implemented |
| PostgreSQL platform metadata | Implemented |
| Background job worker | Implemented |
| Schema-aware ontology discovery | Implemented |
| PDF-to-ontology fabric bridge | Implemented |
| Canonical graph in PostgreSQL | Implemented |
| D3 graph visualization | Implemented |
| Neo4j export adapter | Implemented (optional configuration) |
| Stardog/RDF export adapter | Implemented (optional configuration) |
| Graph-augmented retrieval | Implemented (feature flag) |
| Stardog virtual graphs over warehouses | Planned |
| Neo4j as primary query engine for Weave | Planned |
| Multi-tenant SaaS isolation | Planned |
| Full SSO / RBAC | Planned |

---

## 7. Non-Goals (Current Release)

- Replacing enterprise data warehouses or lakehouses.
- Real-time streaming ingest at sub-second latency (batch and on-demand dominate).
- Full OWL reasoning inside Weave (delegated to Stardog when adopted).
- Hosted multi-tenant SaaS without dedicated deployment architecture review.

---

## 8. Document Navigation

Proceed to [02-application-architecture.md](./02-application-architecture.md) for service decomposition and runtime flows.
