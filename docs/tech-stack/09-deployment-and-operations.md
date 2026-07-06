# Deployment and Operations

## 1. Deployment Models

| Model | Use case | Components |
|-------|----------|------------|
| Local development | Engineer workstation | Backend (uvicorn), frontend (CRA), optional SQLite |
| Docker Compose | Team demo, integration test | backend, frontend, postgres, redis (optional) |
| Production (target) | Enterprise deployment | Container orchestration, managed Postgres, secrets manager |

Weave is designed to run without Neo4j or Stardog. Those systems are optional sidecar or external services configured only when export is required.

---

## 2. Docker Compose Topology

Default `docker-compose.yml` services:

```text
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│  frontend   │────▶│   backend   │────▶│  postgres    │
│  :3000      │     │  :8000      │     │  :5432       │
└─────────────┘     └──────┬──────┘     └──────────────┘
                           │
                    ┌──────▼──────┐
                    │   redis     │  (optional, not required by core app)
                    │   :6379     │
                    └─────────────┘
```

### 2.1 Backend container

| Attribute | Value |
|-----------|-------|
| Build context | ./backend |
| Port | 8000 |
| Health check | GET /health |
| Volumes | uploads, chroma_db, models, data, ontology_data |

### 2.2 Frontend container

| Attribute | Value |
|-----------|-------|
| Build context | ./frontend |
| Port | 3000 |
| Depends on | backend |

### 2.3 PostgreSQL container

| Attribute | Value |
|-----------|-------|
| Image | postgres:15-alpine |
| Database | knowledge_fabric |
| User | knowledge_user |
| Volume | postgres_data (named) |

---

## 3. Environment Variables

### 3.1 Core platform

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| DATABASE_URL | Production yes | — | PostgreSQL connection string |
| KF_DATA_DIR | No | backend/data | JSON state, SQLite fallback path |
| KF_UPLOAD_DIR | No | backend/uploads | PDF and document uploads |
| KF_CHROMA_DIR | No | backend/chroma_db | Chroma persistence |
| KF_ONTOLOGY_DATA_DIR | No | backend/ontology_data | Ontology artifacts |
| KF_MODELS_DIR | No | backend/models | Trained model artifacts |
| ENABLE_JOB_WORKER | No | true | Background job daemon |
| JOB_POLL_INTERVAL_SECONDS | No | 2 | Worker poll interval |
| USE_GRAPH_RETRIEVAL | No | false | Enable graph-augmented retrieval |

### 3.2 Graph export

| Variable | Description |
|----------|-------------|
| GRAPH_STORAGE_BACKEND | postgres, neo4j, stardog, rdf, all |
| NEO4J_URI | bolt://host:7687 |
| NEO4J_USER | Neo4j username |
| NEO4J_PASSWORD | Neo4j password |
| STARDOG_ENDPOINT | Stardog HTTP base URL |
| STARDOG_DATABASE | Target database name |
| STARDOG_USERNAME | Stardog credentials |
| STARDOG_PASSWORD | Stardog credentials |

### 3.3 LLM providers

| Variable | Description |
|----------|-------------|
| OPENAI_API_KEY | OpenAI API access |
| ANTHROPIC_API_KEY | Anthropic API access |
| GEMINI_API_KEY | Google Gemini access |
| DEFAULT_LLM_PROVIDER | openai (default) |

### 3.4 Security

| Variable | Description |
|----------|-------------|
| INBOUND_AUTH_DISABLED | Bypass API key middleware (not for production) |
| INBOUND_AUTH_BYPASS_PATHS | Comma-separated path exemptions |
| SECRET_KEY | Application secret (change in production) |
| KF_CORS_ORIGINS | Additional CORS origins |

### 3.5 Frontend

| Variable | Description |
|----------|-------------|
| REACT_APP_API_URL | Backend URL for browser clients |

---

## 4. Database Initialization

On application startup (`lifespan` in main.py):

1. `init_db()` — SQLAlchemy `create_all` against configured engine
2. `fabric_store.initialize()` — JSON-to-Postgres migration if needed
3. `job_worker.start()` — Background worker thread

Note: Alembic migrations are planned. Current releases rely on schema creation at startup. Review model changes before upgrading production.

### 4.1 SQLite fallback

When `DATABASE_URL` is unset, the platform uses SQLite at:

```
{KF_DATA_DIR}/weave_platform.db
```

Suitable for local development only. Production should always set `DATABASE_URL`.

---

## 5. Health and Readiness

### 5.1 Endpoint

```
GET /health
```

Response includes subsystem checks:

| Check | Description |
|-------|-------------|
| api | Always healthy if endpoint responds |
| database | SELECT 1 against configured engine |
| chroma | Vector service initialization |
| job_worker | Worker thread running state |

### 5.2 Container health checks

Docker Compose configures curl-based probes on backend (:8000/health) and frontend (:3000).

---

## 6. Background Jobs

### 6.1 Job types

| job_type | Handler |
|----------|---------|
| ontology_discovery | Schema or document discovery pipeline |
| graph_build | Canonical graph materialization |
| graph_export | Neo4j / RDF / Stardog push |

### 6.2 Operations

| Action | API |
|--------|-----|
| Enqueue | POST /api/v1/platform/jobs |
| Status | GET /api/v1/platform/jobs/{id} |
| Fabric history | GET /api/v1/platform/fabrics/{id}/jobs |

Jobs persist in PostgreSQL `platform_jobs` table (or SQLite equivalent).

### 6.3 Worker disable

Set `ENABLE_JOB_WORKER=false` when running a dedicated worker process (future split deployment). Current release runs worker in-process with the API server.

---

## 7. Backup and Recovery

### 7.1 PostgreSQL

Standard pg_dump / point-in-time recovery for:

- fabrics, platform_jobs
- ontology_projects, ontology_versions, ontology_elements
- graph_nodes, graph_edges
- ontology_audit_logs

### 7.2 Chroma

Script: `scripts/backup_chroma.py`

Back up `KF_CHROMA_DIR` before major upgrades. Vector index can be rebuilt from source fabrics but at significant re-embedding cost.

### 7.3 File artifacts

Include in backup scope:

- KF_UPLOAD_DIR (PDF fabrics)
- KF_ONTOLOGY_DATA_DIR (ontology uploads)
- KF_DATA_DIR (legacy JSON dual-write backups)

### 7.4 Migration script

`scripts/migrate_json_to_postgres.py` — one-time migration from legacy fabrics.json to PostgreSQL.

---

## 8. Scaling Considerations

| Component | Scale approach |
|-----------|----------------|
| API | Horizontal replicas behind load balancer (shared Postgres required) |
| Job worker | Single active worker recommended until distributed locking is implemented |
| Chroma | Single-writer persistence; consider external vector DB for multi-replica |
| Postgres | Vertical scale first; read replicas for analytics queries (future) |
| Embeddings | CPU-bound; GPU optional for batch re-embedding |

Redis is included in Docker Compose as optional infrastructure but is not required by core application logic in the current release.

---

## 9. Logging and Observability

| Area | Current state |
|------|---------------|
| Application logs | Python logging to stdout |
| Structured JSON logging | Planned (Phase 5) |
| Metrics (Prometheus) | Not implemented |
| Distributed tracing | Not implemented |

Operators should aggregate container stdout via their platform log stack (CloudWatch, Datadog, ELK).

---

## 10. Upgrade Procedure (Recommended)

1. Backup Postgres and Chroma directory
2. Pull new image or code revision
3. Review environment variable additions in release notes
4. Run database migration when Alembic is introduced; until then verify model compatibility
5. Restart backend (triggers init_db and fabric_store migration)
6. Verify GET /health all subsystems healthy
7. Smoke test: create fabric, discover ontology, approve, view canonical graph

---

## 11. Local Development (Non-Docker)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql://...   # optional
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm start
```

---

## 12. External Service Dependencies

| Service | Required | Purpose |
|---------|----------|---------|
| PostgreSQL | Production | Platform metadata and graph |
| OpenAI (or alt LLM) | For query/discovery | LLM synthesis and ontology |
| Neo4j | Optional | Graph export |
| Stardog | Optional | RDF upload |
| Databricks / Snowflake | Per fabric | Source data connectivity |

---

## 13. Next Document

See [10-security-and-governance.md](./10-security-and-governance.md) for authentication, guardrails, and compliance controls.
