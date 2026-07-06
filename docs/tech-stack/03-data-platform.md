# Data Platform

## 1. Data Platform Strategy

Weave employs a polyglot persistence model aligned to access patterns:

| Store | Access pattern | Consistency model |
|-------|----------------|-------------------|
| PostgreSQL | Transactional metadata, graph adjacency, audit | ACID |
| ChromaDB | Approximate nearest neighbor vector search | Eventual (embedded persistence) |
| File system | Blobs, ontology artifacts, model weights | Filesystem durability |
| JSON legacy files | Migration fallback | File-level |

No single database holds all platform state. The control plane (PostgreSQL) references fabric identifiers that partition data in Chroma and on disk.

---

## 2. PostgreSQL (Primary Control Plane)

### 2.1 Deployment

| Environment | Connection |
|-------------|------------|
| Docker Compose | `DATABASE_URL=postgresql://knowledge_user:knowledge_pass@postgres:5432/knowledge_fabric` |
| Local native | `DATABASE_URL` unset → SQLite at `backend/data/weave_platform.db` |
| Production | Managed PostgreSQL 15+ recommended |

ORM: SQLAlchemy 2.0 with `create_all` on startup (Alembic migrations planned for strict versioning).

### 2.2 Core tables

#### fabrics

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR(128) PK | Fabric identifier |
| name | VARCHAR(512) | Display name |
| source_type | VARCHAR(64) | pdf, database, composite, servicenow, … |
| status | VARCHAR(32) | active, training, error |
| model_status | VARCHAR(32) | not_trained, training, trained, failed |
| document_count | INTEGER | Source document count |
| total_chunks | INTEGER | Indexed chunk count |
| tags | JSON | Domain and connector tags |
| connection_info | JSON | Connector metadata, schema hints |
| guardrails | JSON | Classification, PII, compliance |
| ontology_project_id | VARCHAR(64) | Linked ontology project |
| approved_ontology_version_id | VARCHAR(64) | Active approved version |
| ontology_waiver | BOOLEAN | Explicit opt-out flag |
| payload | JSON | Full fabric document (backward compatibility) |
| created_at, updated_at | TIMESTAMP | Audit timestamps |

#### fabric_jobs

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR(64) PK | Job identifier |
| fabric_id | VARCHAR(128) FK | Associated fabric |
| job_type | VARCHAR(64) | ontology_discovery, graph_build, graph_export |
| status | VARCHAR(32) | queued, running, ready, failed |
| progress_percent | FLOAT | 0–100 |
| error_payload | JSON | Failure diagnostics |
| result | JSON | Success artifacts (version_id, run_id, export status) |
| config | JSON | Job input parameters |
| started_at, completed_at | TIMESTAMP | Timing |

#### ontology_projects

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR(64) PK | Project identifier |
| name | VARCHAR(512) | Project name |
| description | TEXT | Optional description |
| domain | VARCHAR(128) | Business domain label |
| fabric_id | VARCHAR(128) | Linked fabric reference |

#### ontology_versions

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR(64) PK | Version identifier |
| project_id | VARCHAR(64) FK | Parent project |
| version_label | VARCHAR(64) | Human label (e.g. draft, 1.0) |
| is_draft | BOOLEAN | Draft flag |
| is_approved | BOOLEAN | Approval flag |
| approved_by | VARCHAR(256) | Approver identity |
| approved_at | TIMESTAMP | Approval timestamp |
| payload | JSON | Full OntologyVersion document |

#### ontology_audit_logs

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR(64) PK | Log entry ID |
| version_id | VARCHAR(64) | Target version |
| action | VARCHAR(64) | approve, reject, edit |
| actor | VARCHAR(256) | User or system |
| details | JSON | Structured context |

### 2.3 Graph tables (canonical knowledge graph)

#### graph_nodes

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR(64) PK | Node identifier |
| fabric_id | VARCHAR(128) | Owning fabric |
| ontology_class_id | VARCHAR(64) | Source ontology class |
| ontology_version_id | VARCHAR(64) | Version binding |
| label | VARCHAR(512) | Display label |
| normalized_name | VARCHAR(512) | Normalized entity name |
| properties | JSON | Attribute type map |
| source_table | VARCHAR(256) | Optional warehouse table |
| source_column | VARCHAR(256) | Optional column |

#### graph_edges

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR(64) PK | Edge identifier |
| fabric_id | VARCHAR(128) | Owning fabric |
| source_node_id | VARCHAR(64) FK | Source node |
| target_node_id | VARCHAR(64) FK | Target node |
| relationship_type | VARCHAR(256) | Ontology relationship name |
| ontology_version_id | VARCHAR(64) | Version binding |
| properties | JSON | Edge metadata |
| confidence | FLOAT | Confidence score |
| evidence_refs | JSON | Source evidence snippets |

#### graph_build_runs

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR(64) PK | Build run identifier |
| fabric_id | VARCHAR(128) | Target fabric |
| ontology_version_id | VARCHAR(64) | Source ontology version |
| status | VARCHAR(32) | queued, ready, failed |
| storage_backend | VARCHAR(32) | postgres, neo4j, stardog, all |
| node_count, edge_count | INTEGER | Materialization statistics |
| export_uris | JSON | External export results |
| built_at | TIMESTAMP | Completion time |

### 2.4 Indexes

Composite indexes on `(fabric_id, ontology_version_id)` for nodes and edges support traversal and graph API queries at fabric scope.

---

## 3. ChromaDB (Vector Store)

### 3.1 Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| KF_CHROMA_DIR | backend/chroma_db | Persistent storage path |
| CHROMA_PERSIST_DIRECTORY | Same as above | Legacy alias |
| MODEL_NAME | sentence-transformers/all-MiniLM-L6-v2 | Embedding model |
| EMBEDDING_DIMENSION | 384 | Vector dimension |

### 3.2 Collection model

Documents are stored per fabric using `source_id` metadata filtering in `vector_service.search_similar_chunks`. Each chunk carries metadata:

- source table, row, column (tabular)
- file name, page number (documents)
- chunk index, similarity rank (query time)

### 3.3 Backup

Script: `scripts/backup_chroma.py` — produces timestamped tar.gz archives of the Chroma directory. Restore by extracting to `KF_CHROMA_DIR` with services stopped.

---

## 4. File System Layout

| Path | Variable | Contents |
|------|----------|----------|
| backend/data/ | KF_DATA_DIR | fabrics.json backup, weave_platform.db (SQLite), backups |
| backend/uploads/ | KF_UPLOAD_DIR | PDF and fabric upload files |
| backend/ontology_data/ | KF_ONTOLOGY_DATA_DIR | Ontology projects, versions, runs (JSON) |
| backend/ontology_data/uploads/ | KF_ONTOLOGY_UPLOAD_DIR | Ontology studio uploads |
| backend/chroma_db/ | KF_CHROMA_DIR | Chroma persistence |
| backend/models/ | KF_MODELS_DIR | Trained model artifacts |

Docker Compose bind-mounts these paths for parity between container and native Uvicorn workflows.

---

## 5. Dual-Write and Migration

`FabricStore` migrates `fabrics.json` to PostgreSQL on first initialization when the database is empty. JSON remains as a backup export format.

Ontology data dual-writes: file persistence (`ontology_persistence_service`) plus PostgreSQL rows in `ontology_versions` for approved serving paths.

Migration script: `scripts/migrate_json_to_postgres.py`.

---

## 6. Data Lifecycle

| Stage | Storage touched |
|-------|-----------------|
| Ingest | uploads/, connection fetch (no local copy for warehouse) |
| Index | chroma_db/, fabrics table |
| Ontology discovery | ontology_data/, ontology_versions |
| Graph build | graph_nodes, graph_edges, graph_build_runs |
| Export | External Neo4j/Stardog; export metadata in graph_build_runs.export_uris |
| Delete fabric | Fabric row, optional Chroma purge (operator script) |

---

## 7. Capacity Planning Guidelines

| Tier | Fabrics | Chroma size | Postgres |
|------|---------|-------------|----------|
| Development | &lt; 20 | &lt; 5 GB | SQLite acceptable |
| Team | 20–200 | 5–50 GB | PostgreSQL 15, 50 GB disk |
| Enterprise | 200+ | 50+ GB | Managed Postgres, Chroma scale-out evaluation |

Schema-level canonical graphs typically contain 10²–10⁴ nodes per fabric. Instance-level materialization is roadmap item P3-12.

---

## 8. Next Document

See [04-source-integrations.md](./04-source-integrations.md) for connector specifications.
