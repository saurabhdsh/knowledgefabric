# API and Integration

## 1. API Foundation

| Attribute | Value |
|-----------|-------|
| Base URL | http://localhost:8000 (development) |
| Version prefix | /api/v1 |
| Protocol | HTTPS in production |
| Format | JSON request/response |
| Documentation | OpenAPI 3 at /docs |

---

## 2. Response Envelope

```json
{
  "success": true,
  "message": "Human-readable status",
  "data": { },
  "error": null
}
```

Errors return appropriate HTTP status codes with `success: false` and `error` or `message` populated.

---

## 3. API Surface by Domain

### 3.1 Knowledge Fabric (`/api/v1/knowledge`)

| Method | Path | Description |
|--------|------|-------------|
| GET | / | List all fabrics |
| POST | /create-pdf-fabric | Create fabric from uploaded PDF/TXT |
| POST | /create-database-fabric | Create fabric from live warehouse connection |
| POST | /create-database-fabric-csv | Create fabric from CSV upload |
| POST | /create-composite-fabric | Merge multiple fabrics |
| POST | /query/{fabric_id} | LLM-synthesized answer |
| POST | /retrieve/{fabric_id} | Retrieval-only (chunks + graph context) |
| GET | /{fabric_id}/knowledge-graph | Exploratory or canonical graph for UI |
| GET | /{fabric_id}/documents | Source document listing |
| PUT | /{fabric_id}/rename | Rename fabric |
| PUT | /{fabric_id}/guardrails | Update governance profile |
| DELETE | /{fabric_id} | Delete fabric |
| POST | /test-database-connection | Validate connector |
| POST | /train-ml-models | Start training job |

### 3.2 Ontology (`/api/v1/ontology`)

| Method | Path | Description |
|--------|------|-------------|
| POST | /projects | Create ontology project |
| POST | /projects/from-fabric | Bootstrap project from fabric |
| GET | /projects/{id} | Get project |
| POST | /projects/{id}/discover | Start discovery run |
| GET | /projects/{id}/runs | List discovery runs |
| GET | /projects/{id}/versions | List versions |
| GET | /projects/{id}/versions/{vid} | Get version detail |
| POST | /review/approve | Approve ontology elements |
| POST | /review/reject | Reject elements |
| GET | /export/{version_id} | Export ontology (json, csv, graph) |
| POST | /upload | Upload ontology artifacts |

### 3.3 Platform (`/api/v1/platform`)

| Method | Path | Description |
|--------|------|-------------|
| POST | /jobs | Enqueue background job |
| GET | /jobs/{job_id} | Job status |
| GET | /fabrics/{fabric_id}/jobs | Fabric job history |
| POST | /fabrics/{fabric_id}/discover-ontology | Trigger ontology discovery |
| POST | /fabrics/{fabric_id}/link-ontology | Link fabric to project |

### 3.4 Graph (`/api/v1/graph`)

| Method | Path | Description |
|--------|------|-------------|
| POST | /ontology/versions/{id}/approve | Approve version + enqueue graph build |
| POST | /fabrics/{id}/graph/build | Materialize canonical graph |
| GET | /fabrics/{id}/graph | Canonical graph payload |
| GET | /fabrics/{id}/graph/neighbors/{node_id} | Traversal |
| POST | /fabrics/{id}/graph/export | Export to neo4j, rdf, stardog |

### 3.5 Search (`/api/v1/search`)

| Method | Path | Description |
|--------|------|-------------|
| POST | / | General search |
| POST | /semantic | Semantic search variant |

### 3.6 Upload (`/api/v1/upload`)

| Method | Path | Description |
|--------|------|-------------|
| POST | / | Upload files for fabric creation |

### 3.7 Training (`/api/v1/training`)

Training lifecycle endpoints for model management.

### 3.8 Database (`/api/v1/database`)

MongoDB-specific connection and preview endpoints.

---

## 4. Authentication

### 4.1 Inbound API key

Middleware: `InboundAPIKeyMiddleware`

| Caller | Requirement |
|--------|-------------|
| Local network (RFC1918, localhost) | X-API-Key optional |
| External (e.g. ngrok) | X-API-Key required |

Keys issued via `scripts/issue_api_key.py`, stored hashed in inbound API key service.

### 4.2 LLM BYOK

Header: `X-LLM-API-Key`  
Required for external `/query` callers. Not required for `/retrieve`.

### 4.3 CORS

Allowed origins: localhost:3000, configurable via `KF_CORS_ORIGINS`. Ngrok subdomain regex supported for development tunnels.

---

## 5. Partner Integration Patterns

### 5.1 Retrieve-only (recommended for agents)

```http
POST /api/v1/knowledge/retrieve/{fabric_id}
Content-Type: application/json
X-API-Key: {inbound_key}

{
  "query": "natural language question",
  "top_k": 5,
  "use_graph": true
}
```

Partner runs own LLM on returned chunks and graph_context.

### 5.2 Full query

```http
POST /api/v1/knowledge/query/{fabric_id}
X-API-Key: {inbound_key}
X-LLM-API-Key: {openai_key}

{
  "query": "...",
  "llm_provider": "openai"
}
```

### 5.3 CLI tooling

| Script | Purpose |
|--------|---------|
| scripts/csnp_agents_cli.py | Classic vs Weave compare demo |
| scripts/csnp_agent_inline.py | Standalone retrieve client |
| scripts/issue_api_key.py | API key administration |

---

## 6. Webhook and Event Model

Push webhooks for job completion are planned. Current integration pattern: poll `GET /api/v1/platform/jobs/{job_id}` or fabric job list.

---

## 7. Rate Limiting and Quotas

Production deployments should place API gateway rate limits in front of Weave. Internal rate limiting is not enforced in the application layer in the current release.

---

## 8. Versioning Policy

Breaking changes require `/api/v2` prefix. Additive changes (new fields, optional parameters) are permitted within v1.

---

## 9. Next Document

See [08-frontend-stack.md](./08-frontend-stack.md) for client application architecture.
