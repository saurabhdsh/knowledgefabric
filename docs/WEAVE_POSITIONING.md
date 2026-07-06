# Weave Platform Positioning

## Executive Positioning (Non-Technical)

### One-line category
Weave is a **Hybrid Retrieval Intelligence Platform**: a production-ready retrieval core with graph-aware schema understanding and agent-ready APIs.

### One-line value proposition
Weave helps enterprises get grounded answers from complex operational data faster than full graph programs and with more semantic depth than plain vector search.

### Customer-facing narrative
- **Reliable by default:** deterministic retrieval APIs return evidence-first context.
- **Smarter than plain RAG:** ontology discovery maps entities and relationships across heterogeneous schemas.
- **Flexible for any AI stack:** customers can use their own LLMs and agent frameworks (BYOK pattern).
- **Enterprise-ready controls:** API-key protected access and external endpoint patterns for partner integrations.

### Best-fit business outcomes
- Faster onboarding of schema-heavy data domains (payer, claims, care, ITSM, compliance).
- Better analyst and operator productivity through grounded retrieval.
- Lower deployment risk versus full agentic orchestration from day one.

### 20-second talk track
Weave is not just a vector chatbot. It combines classic RAG speed and reliability with ontology-driven understanding of entities and relationships in enterprise schemas. Teams consume it through secure APIs and can plug in any LLM or agent layer using their own keys.

---

## CTO Positioning (Architecture View)

### Category statement
**Classic RAG core + graph-enriched metadata layer + agent-ready serving interface**

### Architecture layers
1. **Ingestion and Fabric Build**
   - Data sources: Databricks, Snowflake, CSV and other tabular systems.
   - Knowledge Fabric created per domain/workload.

2. **Retrieval Core (Classic RAG Backbone)**
   - Chunking and embeddings.
   - Vector index for semantic top-k retrieval.
   - Retrieval-first APIs for grounded context delivery.

3. **Semantic Enrichment Layer (Graph-aware)**
   - Ontology discovery extracts entities, attributes and inferred relationships.
   - Domain signals improve interpretability and retrieval quality.
   - Relationship metadata augments context selection and downstream reasoning.

4. **Serving and Integration Layer**
   - API endpoints for retrieval and fabric metadata.
   - Secure inbound access using `X-API-Key`.
   - External-access patterns via HTTPS tunneling or cloud deployment.

5. **LLM and Agent Consumption Layer**
   - BYOK model: caller controls model provider/key.
   - Works with single-agent or multi-agent orchestrators.
   - Enables provider portability (OpenAI, Anthropic, Gemini, custom/local).

### Why this architecture is pragmatic
- Delivers production value with deterministic behavior before committing to full graph/agent complexity.
- Preserves future path to deeper graph reasoning and orchestration while keeping current ops manageable.
- Decouples retrieval reliability from LLM/provider volatility.

---

## Competitive Matrix (Classic vs Graph vs Agentic vs Weave)

| Dimension | Classic RAG | Graph RAG | Agentic RAG | Weave (Current Position) |
|---|---|---|---|---|
| Primary strength | Speed and cost efficiency | Relationship-aware retrieval | Multi-step reasoning and tool use | Balanced reliability + semantic depth |
| Data modeling effort | Low | Medium to high | Medium to high | Medium (incremental via ontology discovery) |
| Retrieval grounding | Strong | Strong | Varies by orchestration quality | Strong (retrieval-first API pattern) |
| Relationship understanding | Limited | Strong | Potentially strong | Moderate to strong (inferred ontology layer) |
| Operational complexity | Low | Medium | High | Medium |
| Time to value | Fast | Moderate | Slower | Fast to moderate |
| Hallucination control | Good when evidence-coupled | Good | Variable | Good (evidence-first, caller-side synthesis optional) |
| Best for | FAQ/support/search | Connected-entity domains | Research/workflow automation | Enterprise schema-heavy copilots and agent backends |

### Positioning summary
- **Classic RAG:** best when data is simple and speed is the primary requirement.
- **Graph RAG:** best when explicit relationships are central to answer quality.
- **Agentic RAG:** best when tasks require planning, tools and iterative reasoning.
- **Weave:** best when teams need trustworthy retrieval now, with graph-aware semantics and an agent-compatible path.

---

## Messaging Snippets for Sales and Partner Calls

### Elevator pitch
Weave gives you production-grade retrieval plus schema intelligence. You get grounded evidence from enterprise data, and you keep freedom to choose any LLM or agent layer.

### Objection handling: "Why not just build full Graph RAG?"
Full graph systems can deliver deep relationship reasoning, but they add modeling and operational overhead. Weave provides an incremental path: immediate value with retrieval reliability, then semantic depth through ontology enrichment.

### Objection handling: "Why not go fully agentic now?"
Agentic systems are powerful but introduce orchestration complexity and variability. Weave keeps the data/retrieval substrate deterministic and secure so agent layers can be added safely and progressively.

---

## Recommended Label to Use Publicly

Use this exact phrase in decks, docs and demos:

**Weave is a Hybrid Retrieval Intelligence Platform: Classic RAG core, graph-aware ontology enrichment, and secure agent-ready APIs.**
