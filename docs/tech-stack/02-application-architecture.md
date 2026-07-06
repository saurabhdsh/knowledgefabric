# Application Architecture

## 1. Runtime Topology

| Component | Technology | Port (default) | Responsibility |
|-----------|------------|----------------|----------------|
| Backend API | FastAPI + Uvicorn | 8000 | REST APIs, job worker, business logic |
| Frontend SPA | React (Create React App) | 3000 | Operator console, ontology studio, graph UI |
| PostgreSQL | 15 Alpine | 5432 | Platform metadata, ontology, canonical graph |
| Redis | 7 Alpine | 6379 | Optional cache profile (not required for core path) |

Native development may run Uvicorn and `npm start` directly with bind-mounted data directories under `backend/`.

---

## 2. Backend Module Structure

```text
backend/app/
├── main.py                 Application entry, lifespan, health checks
├── core/
│   ├── config.py           Environment-backed settings (Pydantic Settings)
│   └── security.py         Inbound API key middleware, CORS helpers
├── db/
│   ├── session.py          SQLAlchemy engine and session factory
│   └── models.py           Platform ORM models
├── api/v1/
│   ├── api.py              Router aggregation
│   └── endpoints/
│       ├── knowledge.py    Fabric CRUD, ingest, query, retrieve, graph view
│       ├── ontology.py     Projects, discovery, review, export
│       ├── platform.py     Jobs, fabric-ontology triggers
│       ├── graph.py        Graph build, approve, export, traversal
│       ├── database.py     MongoDB and connector helpers
│       ├── search.py       Semantic search
│       ├── training.py     Model training lifecycle
│       └── upload.py       File upload handlers
├── services/
│   ├── platform/           Fabric store, job service, job worker
│   ├── ontology/           Discovery pipeline, schema analyzer, persistence
│   ├── graph/              Materialization, graph store, Neo4j/RDF adapters
│   ├── retrieval/          Retrieval orchestrator
│   ├── vector_service.py   Chroma embedding and search
│   ├── document_service.py PDF/text chunking
│   ├── knowledge_graph_service.py  Exploratory co-occurrence graph
│   └── training_service.py ML training hooks
└── models/                 Pydantic domain models (knowledge, ontology)
```

---

## 3. Application Layers

### 3.1 API Layer

- Versioned under `/api/v1`.
- Uniform response envelope: `{ success, message, data, error }`.
- OpenAPI documentation at `/docs` and `/redoc`.
- Health endpoint at `/health` with subsystem checks (database, Chroma, job worker).

### 3.2 Service Layer

Business logic is encapsulated in services invoked by route handlers. Long-running work is delegated to the job worker rather than blocking HTTP threads.

### 3.3 Persistence Layer

| Concern | Mechanism |
|---------|-----------|
| Fabrics, jobs, ontology versions, graph | SQLAlchemy ORM → PostgreSQL or SQLite |
| Legacy / backup | JSON files (`fabrics.json`) dual-written during migration |
| Ontology file artifacts | `ontology_data/` directory tree |
| Vector embeddings | Chroma persistent client |
| Uploaded fabric files | `uploads/` directory |
| Trained models | `models/` directory |

### 3.4 Integration Layer

Connectors invoke external systems (Databricks REST, Snowflake JDBC, psycopg2, mysql.connector, pymongo) and normalize rows into a unified chunk format before vector indexing.

---

## 4. Job Processing Architecture

### 4.1 Job types

| Job Type | Trigger | Handler outcome |
|----------|---------|-----------------|
| ontology_discovery | Fabric ready, manual API, UI panel | Ontology version draft persisted |
| graph_build | Ontology approval, manual API | Canonical graph in PostgreSQL |
| graph_export | Manual API, UI export buttons | Neo4j push and/or RDF generation |
| fabric_ingest | Planned expansion | Full async ingest pipeline |

### 4.2 State machine

```text
queued → running → (indexing | training) → ready | failed
```

Progress percentage and error payloads are persisted in `fabric_jobs` for UI polling.

### 4.3 Worker model

A daemon thread polls the job queue at configurable interval (`JOB_POLL_INTERVAL_SECONDS`, default 2s). Production deployments may replace this with Redis Queue, Celery, or ARQ without changing job record schema.

---

## 5. Ontology Discovery Pipeline

```text
Source artifacts OR schema profile
        │
        ▼
┌───────────────────┐
│ Schema analyzer     │  ← LLM + rules (tabular)
│ (Layer 1)           │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Concept extractor │  ← Rules (documents)
│ Semantic chunker  │
│ LLM ontology svc  │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Classifier ·       │
│ Relation inference │
│ Attribute mapper   │
│ Assembler          │
│ Validator          │
└─────────┬─────────┘
          │
          ▼
   OntologyVersion (draft)
          │
          ▼
   Human review / approve
```

Fabric-linked PDF discovery uses `fabric_artifact_bridge` to resolve files from `uploads/` or materialize vector chunks as XML in `ontology_data/uploads/`.

---

## 6. Graph Materialization Flow

```text
Approved OntologyVersion
        │
        ▼
GraphMaterializationService
        │
        ├── Clear prior graph for (fabric_id, ontology_version_id)
        ├── Map classes → graph_nodes
        ├── Map relationships → graph_edges
        ├── Persist to PostgreSQL
        └── Optional: neo4j_adapter · rdf_adapter · stardog push
        │
        ▼
GraphBuildRun record (status, counts, export_uris)
```

---

## 7. Retrieval Orchestration Flow

```text
User query
    │
    ├─► Vector search (Chroma top-k)
    │
    ├─► Entity linking (keyword match against graph node labels)
    │
    ├─► Graph expansion (1–2 hop neighbors from PostgreSQL)
    │
    ├─► Context merge (graph summary + chunks)
    │
    └─► LLM synthesis (/query only) with ontology summary in prompt
```

Controlled by `USE_GRAPH_RETRIEVAL` environment variable and per-request `use_graph` override on `/retrieve`.

---

## 8. Request Path Examples

### Create database fabric

```text
Client → POST /api/v1/knowledge/create-database-fabric
       → Connector fetch rows
       → document_service.process_database_data
       → vector_service.add_documents
       → fabric_store.save
       → job_service.enqueue(ontology_discovery)
       → Response with fabric_id
```

### Approve ontology and build graph

```text
Client → POST /api/v1/graph/ontology/versions/{id}/approve
       → ontology_db_repository.approve_version
       → job_service.enqueue(graph_build)
       → Worker → graph_materialization_service.materialize
```

---

## 9. Cross-Cutting Concerns

| Concern | Implementation |
|---------|----------------|
| Configuration | `app/core/config.py`, `.env`, `KF_*` path overrides |
| Logging | Python standard logging (structured enrichment planned) |
| Error handling | HTTPException with envelope; job errors in `error_payload` |
| Idempotency | Graph rebuild clears version-scoped nodes before insert |

---

## 10. Next Document

See [03-data-platform.md](./03-data-platform.md) for database schemas, Chroma configuration, and persistence policies.
