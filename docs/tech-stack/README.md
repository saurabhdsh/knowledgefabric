# Weave Platform — Technical Documentation Index

Document suite version: 1.0  
Last updated: 2026-05-29  
Classification: Internal / Technical Architecture

---

## Purpose

This directory contains the authoritative technical description of the Weave platform (Knowledge Fabric). The documentation is intended for engineering leadership, platform architects, security reviewers, and implementation teams.

Weave is an enterprise ontology intelligence and knowledge graph factory: it connects heterogeneous data sources, discovers semantic structure, governs approval of ontologies, materializes canonical knowledge graphs, and serves graph-augmented retrieval for downstream analytics and AI consumption.

---

## Document Map

| Document | Title | Scope |
|----------|-------|-------|
| [01-overview.md](./01-overview.md) | Platform Overview | Capabilities, design principles, logical architecture |
| [02-application-architecture.md](./02-application-architecture.md) | Application Architecture | Services, modules, request flows, job processing |
| [03-data-platform.md](./03-data-platform.md) | Data Platform | PostgreSQL, SQLite, Chroma, file persistence, schemas |
| [04-source-integrations.md](./04-source-integrations.md) | Source Integrations | Databricks, Snowflake, relational DBs, documents, APIs |
| [05-ontology-and-graph.md](./05-ontology-and-graph.md) | Ontology and Knowledge Graph | Discovery, governance, graph storage, Neo4j, Stardog, RDF |
| [06-retrieval-and-ai.md](./06-retrieval-and-ai.md) | Retrieval and AI | Embeddings, vector search, LLM synthesis, orchestration |
| [07-api-and-integration.md](./07-api-and-integration.md) | API and Integration | REST surface, authentication, partner consumption |
| [08-frontend-stack.md](./08-frontend-stack.md) | Frontend Stack | React application, visualization, platform UI |
| [09-deployment-and-operations.md](./09-deployment-and-operations.md) | Deployment and Operations | Docker, configuration, health, backup, scaling path |
| [10-security-and-governance.md](./10-security-and-governance.md) | Security and Governance | Auth, guardrails, audit, data classification |

---

## Related Documents (Repository Root)

| Path | Description |
|------|-------------|
| docs/WEAVE_POSITIONING.md | Product and market positioning |
| docs/PRODUCTION_PLATFORM_ROADMAP.md | Implementation roadmap and phase plan |
| docs/ENHANCEMENT_UNIVERSAL_SCHEMA_UNDERSTANDING.md | Ontology discovery architecture (Layers 1–3) |
| backend/docs/ONTOLOGY_MODULE_README.md | Ontology module layout (if present) |

---

## Technology Summary (At a Glance)

| Layer | Primary Technologies |
|-------|---------------------|
| API | Python 3.11, FastAPI, Uvicorn, Pydantic v2 |
| Application data | PostgreSQL 15 (production), SQLite (local fallback) |
| Vector retrieval | ChromaDB, sentence-transformers (all-MiniLM-L6-v2) |
| Graph storage (in-platform) | PostgreSQL property-graph tables |
| Graph export (enterprise) | Neo4j (Cypher), Stardog/RDF (Turtle, JSON-LD) |
| Frontend | React 18, TypeScript, Tailwind CSS, D3.js v7 |
| Container runtime | Docker Compose |
| LLM providers | OpenAI (primary), Anthropic, Google Gemini (configurable) |

---

## Conventions Used in This Suite

- Diagrams use ASCII or Mermaid where clarity benefits from visualization.
- Environment variables are referenced in `UPPER_SNAKE_CASE`.
- API paths are documented relative to the base URL (default `http://localhost:8000/api/v1`).
- “Implemented” denotes capability present in the codebase; “Planned” denotes roadmap items documented in PRODUCTION_PLATFORM_ROADMAP.md.

---

## Maintenance

Update this suite when material changes occur to storage backends, connector support, API contracts, or deployment topology. The document owner should align version notes with release tags or sprint completion records.
