# Ontology and Knowledge Graph

## 1. Scope

This document describes how Weave discovers ontologies, governs versions, materializes knowledge graphs, and integrates with enterprise graph engines (Neo4j, Stardog).

Weave is the ontology intelligence layer. External graph databases are optional consumption targets, not the in-platform source of truth for serving the operator UI and retrieval APIs.

---

## 2. Ontology Domain Model

### 2.1 Core elements

| Element | Description |
|---------|-------------|
| OntologyClass | Entity or concept (e.g. Member, Claim, Incident) |
| OntologyRelationship | Directed relationship between two classes |
| OntologyAttribute | Property belonging to a class |
| OntologyConstraint | Business rule or cardinality constraint |
| OntologyEvidence | Traceability link to source table, column, page, or snippet |

### 2.2 Version lifecycle

```text
draft → reviewed → approved | rejected
```

Approved versions are immutable. Changes require a new version and re-approval. Graph builds bind exclusively to `approved_ontology_version_id` on the fabric record.

### 2.3 Project linkage

| Link | Storage |
|------|---------|
| fabric.ontology_project_id | fabrics table |
| fabric.approved_ontology_version_id | fabrics table |
| project.fabric_id | ontology_projects table |

---

## 3. Discovery Architecture

### 3.1 Layer 1 — Schema-aware analysis (tabular)

Input: table name, column list, types, sample rows (5–20).

Processing:

1. Rule-based inference (primary keys, foreign key patterns, column typing)
2. LLM schema analysis (OpenAI via `llm_ontology_service` patterns)
3. Merge and deduplication

Module: `schema_analyzer.py`  
Orchestrator entry: `run_schema_discovery`

### 3.2 Layer 2 — Document analysis

Input: PDF, DOCX, XML, or materialized XML from fabric chunks.

Pipeline stages:

| Stage | Module |
|-------|--------|
| Artifact load | artifact_loader, fabric_artifact_bridge |
| Text extraction | pdf_processor, docx_processor, xml_processor |
| Chunking | semantic_chunker |
| Concept extraction | concept_extractor |
| LLM enrichment | llm_ontology_service |
| Classification | ontology_classifier |
| Relation inference | relation_inference_engine |
| Attribute mapping | attribute_mapper |
| Assembly | ontology_assembler |
| Validation | ontology_validator |

Orchestrator entry: `run_discovery`

### 3.3 Layer 3 — Domain packs (optional)

Pluggable rule boosters for healthcare, ITSM, pharma. Rules augment but do not replace Layer 1 LLM schema analysis in the production target state.

---

## 4. Governance and Audit

| Control | Implementation |
|---------|----------------|
| Element-level approve/reject | POST /api/v1/ontology/review/approve |
| Version-level approve | POST /api/v1/graph/ontology/versions/{id}/approve |
| Audit trail | ontology_audit_logs table |
| Pre-approve validation | ontology_validator gates |
| Evidence on relationships | Required for production approval policy |

---

## 5. Knowledge Graph Types

### 5.1 Exploratory graph

| Attribute | Value |
|-----------|-------|
| Source | knowledge_graph_service (co-occurrence from chunks) |
| graph_type | exploratory |
| Use | Discovery aid, legacy visualization |
| Persistence | Computed on request (not canonical) |

### 5.2 Canonical graph

| Attribute | Value |
|-----------|-------|
| Source | GraphMaterializationService from approved ontology |
| graph_type | canonical |
| Storage | PostgreSQL graph_nodes, graph_edges |
| Use | Production UI, traversal API, graph-augmented retrieval |
| Versioning | Tagged with ontology_version_id |

The D3 UI prefers canonical graph when `approved_ontology_version_id` exists and node count &gt; 0.

---

## 6. In-Platform Graph Storage (PostgreSQL)

### 6.1 Role

PostgreSQL is the authoritative graph store for Weave operations:

- GET /api/v1/graph/fabrics/{id}/graph
- GET /api/v1/knowledge/{id}/knowledge-graph (canonical branch)
- graph_store.get_neighbors (1–3 hops)
- RetrievalOrchestrator entity linking and expansion

### 6.2 Graph model

Schema-level graph (Phase 3 v1):

- One node per approved ontology class
- One edge per approved relationship
- Properties JSON holds attribute type map from ontology attributes

Instance-level graph (roadmap P3-12):

- Row-level nodes (e.g. Member M000375)
- Higher volume; deferred until schema graph is stable

### 6.3 Traversal API

```
GET /api/v1/graph/fabrics/{fabric_id}/graph/neighbors/{node_id}?hops=1
```

Returns nodes and edges within hop distance on the canonical graph.

---

## 7. Neo4j Integration (Export Target)

### 7.1 Role

Neo4j is an optional downstream property graph engine for enterprise teams using Cypher, Bloom, or Graph Data Science.

Weave does not query Neo4j for operator UI or `/retrieve` in the current release.

### 7.2 Configuration

| Variable | Description |
|----------|-------------|
| NEO4J_URI | bolt://host:7687 |
| NEO4J_USER | Default neo4j |
| NEO4J_PASSWORD | Required for export |
| GRAPH_STORAGE_BACKEND | neo4j or all triggers export on build |

### 7.3 Export behavior

Module: `neo4j_adapter.py`

1. Read canonical graph from PostgreSQL
2. DELETE existing WeaveNode nodes for graph_key `{fabric_id}:{ontology_version_id}`
3. CREATE WeaveNode nodes with label, normalized_name, fabric_id
4. CREATE WEAVE_REL relationships with type property

If Neo4j is not configured, export returns `status: skipped` with Cypher preview comments.

### 7.4 Trigger paths

- Automatic on graph build when GRAPH_STORAGE_BACKEND includes neo4j
- POST /api/v1/graph/fabrics/{id}/graph/export with targets: ["neo4j"]
- UI: Export Neo4j button on Knowledge Graph platform panel

---

## 8. Stardog and RDF Integration (Export Target)

### 8.1 Role

Stardog is an optional semantic graph platform for RDF, SPARQL, reasoning, and (in full Stardog deployments) virtual graphs over warehouses.

Current Weave integration: RDF generation and HTTP upload. Virtual graph mappings over Databricks/Snowflake are planned, not implemented.

### 8.2 Configuration

| Variable | Description |
|----------|-------------|
| STARDOG_ENDPOINT | http://host:5820 |
| STARDOG_DATABASE | Database name |
| STARDOG_USERNAME | Admin user |
| STARDOG_PASSWORD | Credentials |
| GRAPH_STORAGE_BACKEND | stardog triggers upload on build |

### 8.3 RDF generation

Module: `rdf_adapter.py`

| Format | Namespace |
|--------|-----------|
| Turtle | http://weave.ai/ontology# |
| JSON-LD | Same namespace with @graph array |

Entities become `weave:Entity` resources. Relationships become weave-prefixed predicates.

### 8.4 Stardog upload

HTTP POST to:

```
{STARDOG_ENDPOINT}/{STARDOG_DATABASE}/data?graph-uri=weave:{fabric_id}
```

Content-Type: text/turtle

### 8.5 Trigger paths

- Automatic on graph build when GRAPH_STORAGE_BACKEND=stardog
- POST /api/v1/graph/fabrics/{id}/graph/export with targets: ["rdf"] or ["stardog"]
- UI: Export RDF button (generates RDF; Stardog upload requires server config)

---

## 9. Export Format Comparison

| Capability | PostgreSQL | Neo4j | Stardog/RDF |
|------------|------------|-------|-------------|
| Weave UI source of truth | Yes | No | No |
| Graph-augmented retrieval | Yes | No | No |
| Cypher queries | No | Yes | No |
| SPARQL queries | No | No | Yes |
| Virtual warehouse data | No | No | Yes (Stardog product) |
| Setup complexity | Low | Medium | Medium–High |

---

## 10. Ontology Export (Portable Formats)

Independent of graph materialization, OntologyExportService provides:

| Format | Endpoint |
|--------|----------|
| JSON | /api/v1/ontology/export/{version_id}?format=json |
| CSV | format=csv |
| Graph schema | format=graph |
| Canonical model | format=canonical |

These exports support integration with external modeling tools and do not require Neo4j or Stardog.

---

## 11. End-to-End Graph Pipeline

```text
Source → Fabric → Ontology discovery → Review → Approve version
    → graph_build job → PostgreSQL canonical graph
    → Optional: Neo4j export · RDF export · Stardog upload
    → D3 visualization · Retrieval orchestrator · Partner APIs
```

---

## 12. Next Document

See [06-retrieval-and-ai.md](./06-retrieval-and-ai.md) for embedding, LLM, and retrieval orchestration details.
