# Weave Platform — 10-Slide Presentation Guide

Document purpose: Slide prompts, narratives, and talking points for a single 10-slide Weave presentation.

Audience: Executives, enterprise buyers, solutions architects, partners.

Duration: 15–20 minutes (plus optional 10-minute demo).

Last updated: 2026-05-29

---

## How to Use This Document

Each slide includes:

- Slide title — headline for the slide
- Key message — one idea the audience should remember
- Talking points — speaker notes or bullet content
- Visual suggestion — diagram or layout direction

Canonical positioning (use on title slide or speaker intro):

Weave is a Hybrid Retrieval Intelligence Platform: a production-ready retrieval core with graph-aware schema understanding, ontology governance, and agent-ready APIs.

---

## Slide 1 — Title

Slide title: Weave — Hybrid Retrieval Intelligence for Enterprise Data

Key message: Weave turns complex operational data into governed, queryable knowledge that any AI application can trust.

Talking points:

- Ontology discovery and knowledge graph factory for enterprise domains
- Grounded retrieval from Databricks, Snowflake, databases, and documents
- Secure APIs for copilots, agents, and analytics teams
- Deploy on your infrastructure with your LLM keys

Visual suggestion: Title, tagline, three icons — data sources → Weave → AI consumers.

Speaker note (20 seconds):

Weave is not a vector chatbot. It combines classic RAG reliability with ontology-driven understanding of entities and relationships — consumed through secure APIs with any LLM or agent stack.

---

## Slide 2 — The Problem

Slide title: Enterprise AI Stalls on Complex Data

Key message: Schema-heavy domains need relationship understanding and governance, not just semantic similarity.

Talking points:

- Data spans warehouses, lakes, PDFs, and ops systems with inconsistent schemas
- Plain RAG finds similar text but misses relationships (member → claim → provider)
- Full graph programs need months of manual modeling before first value
- Agentic stacks add orchestration before retrieval is dependable
- Compliance requires approved semantics and audit trails, not black-box embeddings

Visual suggestion: Gap diagram — Classic RAG (fast, shallow) | Graph programs (deep, slow) | Weave fills the middle.

---

## Slide 3 — Why Weave

Slide title: Why Weave

Key message: Trustworthy retrieval now, with a governed path to semantic depth.

Talking points:

| Pillar | What it means |
|--------|-----------------|
| Reliable by default | Evidence-first APIs return chunks and context before LLM synthesis |
| Smarter than plain RAG | Auto ontology discovery maps entities, attributes, relationships |
| Governance built in | Analyst approval, immutable versions, audit trails |
| Agent-ready | BYOK — OpenAI, Anthropic, Gemini, or your stack |
| Incremental maturity | Start with retrieval; add canonical graphs and export when ready |
| Source agnostic | Warehouses, databases, PDFs, composite domains — one platform |

Executive one-liner:

Weave delivers grounded answers from complex operational data faster than full graph programs and with more semantic depth than plain vector search.

Visual suggestion: Five pillars around a central Weave hub.

---

## Slide 4 — Platform Features

Slide title: What Weave Delivers

Key message: End-to-end from raw source to governed knowledge graph to AI consumption.

Talking points:

| Capability | Value |
|------------|-------|
| Knowledge Fabric | One bounded domain per workload — claims, members, incidents |
| Multi-source ingest | Databricks, Snowflake, Postgres, MySQL, MongoDB, CSV, PDF, DOCX, XML |
| Semantic indexing | Chunking + embeddings for production RAG recall |
| Ontology discovery | Schema LLM + rules for tables; document pipeline for PDFs |
| Ontology studio | Review, approve, reject — humans stay in control |
| Canonical knowledge graph | Approved ontology → durable schema-level graph |
| Graph visualization | Interactive D3 graph in operator console |
| Graph-augmented retrieval | Vector + entity linking + neighborhood expansion |
| Query and retrieve APIs | Full Q&A or retrieval-only for external agents |
| Background jobs | Observable discovery, graph build, export |
| Fabric guardrails | Topics, blocked terms, citation policies |
| Enterprise export | Optional push to Neo4j or Stardog/RDF |

Visual suggestion: Four quadrants — Ingest · Understand · Govern · Serve.

---

## Slide 5 — How It Works

Slide title: Source to Governed Knowledge in One Flow

Key message: Connect, discover, approve, graph, retrieve — without months of manual modeling.

Talking points:

```text
Connect source → Create Knowledge Fabric → Chunk + embed
→ Auto ontology discovery → Analyst review + approval
→ Canonical graph build → D3 visualization
→ Retrieve / query APIs → Optional export to Neo4j or Stardog
```

Two API modes:

| Mode | Endpoint | Best for |
|------|----------|----------|
| Retrieve only | POST /retrieve/{fabric_id} | Agents that run their own LLM |
| Full query | POST /query/{fabric_id} | Direct Q&A with BYOK |

Demo hook (if live):

Connect one warehouse table → discover ontology → approve → show canonical graph → run one grounded question.

Visual suggestion: Horizontal pipeline with five numbered stages.

---

## Slide 6 — Knowledge Graph and Ontology

Slide title: Governed Semantics, Not Guesswork

Key message: Approved ontology becomes a canonical graph — the production truth for UI and retrieval.

Talking points:

- Exploratory graph: co-occurrence from chunks — useful for discovery only
- Canonical graph: built only from approved ontology versions
- In-platform storage: PostgreSQL (source of truth for operators and retrieval)
- Traversal API: neighborhood expansion for graph-augmented answers
- Optional export: Neo4j (Cypher) or Stardog/RDF (Turtle, JSON-LD) for downstream analytics

Clarification for technical audiences:

Neo4j and Stardog are export targets. Weave does not require them on day one.

Visual suggestion: Draft ontology → Approved version → Canonical graph badge on D3 view.

---

## Slide 7 — Enterprise Scalability

Slide title: Built to Scale with Your Maturity

Key message: Start fast with retrieval; scale governance and graph export as requirements grow.

Talking points:

| Dimension | Approach |
|-----------|----------|
| Data volume | Chunked warehouse ingest; configurable caps for very large catalogs |
| Source diversity | Unified fabric model across all connector types |
| Metadata durability | PostgreSQL — fabrics, jobs, ontology, graph tables |
| Vector index | Chroma with backup; path to external vector DB |
| Async operations | Background jobs with UI status — discovery, build, export |
| API tier | Stateless FastAPI; horizontal scale behind load balancer |
| Deployment | Docker Compose for teams; containers + managed Postgres for production |
| Security | API keys, fabric guardrails, ontology audit logs |
| Maturity path | SQLite dev → Postgres prod → canonical graph → Neo4j/Stardog export |

Scalability talk track:

Do not boil the ocean. One fabric on Postgres and Chroma delivers grounded retrieval in days. Add approval workflows and canonical graphs as governance matures. Export when your graph analytics practice is ready.

Visual suggestion: Staircase — Retrieve → Ontology → Canonical graph → Enterprise export.

---

## Slide 8 — Architecture and Integrations

Slide title: Control Plane Above Your Stack

Key message: Weave sits above warehouses and LLMs — it does not replace them.

Talking points:

```text
Sources (Databricks · Snowflake · DBs · PDF)
    → Weave (FastAPI · Ontology · Graph · Retrieval)
        → PostgreSQL (metadata + canonical graph)
        → Chroma (embeddings)
        → Optional: Neo4j · Stardog
    → Consumers (copilots · agents · BI · partners)
```

Technology summary:

| Layer | Stack |
|-------|-------|
| API | Python 3.11, FastAPI, Uvicorn |
| Data | PostgreSQL 15, ChromaDB, sentence-transformers |
| Graph | PostgreSQL in-platform; Neo4j/Stardog export |
| UI | React 18, TypeScript, D3.js v7 |
| LLM | OpenAI, Anthropic, Gemini (BYOK supported) |

Competitive position (one line):

More reliable than plain RAG, faster to value than full graph programs, more deterministic than agent-first stacks.

Visual suggestion: Layer cake — sources, Weave semantic layer, AI consumers.

---

## Slide 9 — Security, Governance, and Fit

Slide title: Enterprise-Ready Controls

Key message: Approved semantics, secure APIs, and self-hosted deployment under your policies.

Talking points:

Security and governance:

- Inbound API key authentication for external access
- BYOK for LLM keys — customer controls model and spend
- Fabric guardrails — topics, blocked terms, citations
- Immutable approved ontology versions with audit logs
- Self-hosted — data residency under customer control

Where Weave wins:

| Domain | Example |
|--------|---------|
| Healthcare / payer | Members, claims, providers |
| Pharma | Trials, documents, adverse events |
| ITSM | Incidents, changes, CMDB |
| Compliance | Policy PDFs → ontology → graph |

Common objection (one slide answer):

"Why not full Graph RAG?" — Full graph programs add months of modeling. Weave delivers retrieval immediately and grows into governed graphs incrementally.

Visual suggestion: Shield with Access · Governance · Audit.

---

## Slide 10 — Next Steps

Slide title: Start with One Fabric, One Domain

Key message: Prove grounded retrieval in your environment before scaling across the enterprise.

Talking points:

Pilot in three steps:

1. Connect — one production source (warehouse table or PDF domain)
2. Govern — discover ontology, analyst approval, canonical graph
3. Serve — retrieve API into one copilot or agent; compare vs plain vector baseline

Pilot success criteria:

- Approved ontology version with sign-off
- Canonical graph visible in UI
- Ten golden questions answered with measurable grounding improvement

Suggested CTAs:

| Audience | Action |
|----------|--------|
| Executive | Approve single-domain pilot |
| Technical | Architecture review — sources, Postgres, API wiring |
| Partner | Retrieve API workshop + sample agent |
| Security | Data-flow and BYOK review |

Visual suggestion: Connect → Govern → Serve footer with contact / scheduling line.

---

## Speaker Notes — Opening (45 seconds)

Enterprise AI initiatives stall when data is complex and schemas do not align. Vector search alone cannot answer relationship-dependent questions. Full graph programs take months. Weave is the hybrid path: connect your sources, discover ontology automatically, put analysts in control of approval, materialize a canonical knowledge graph, and serve grounded context through secure APIs. You keep your warehouse, your LLM keys, and your policies. Weave is the semantic layer that makes AI trustworthy.

---

## Speaker Notes — Closing (20 seconds)

Weave is the control plane for enterprise knowledge — ingest, understand, govern, graph, retrieve. Ten slides, one pilot, one domain. We can walk through a live fabric from source to canonical graph in the demo.

---

## Optional Demo (Not a Slide)

If time allows after slide 10, run this 8-minute flow:

1. Open Fabrics — show fabric from warehouse or PDF
2. Trigger ontology discovery — show job progress
3. Approve version in ontology workspace
4. Open knowledge graph — canonical badge, D3 view
5. Run retrieve or query — show graph-augmented answer

---

## Related Documents

| Document | Use for |
|----------|---------|
| docs/WEAVE_POSITIONING.md | Messaging and objection depth |
| docs/tech-stack/README.md | Technical appendix if asked |
| docs/tech-stack/01-overview.md | Architecture diagram source |
