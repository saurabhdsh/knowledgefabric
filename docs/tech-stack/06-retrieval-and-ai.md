# Retrieval and AI

## 1. Retrieval Strategy

Weave implements hybrid retrieval intelligence:

| Mode | Mechanism | Endpoint |
|------|-----------|----------|
| Vector recall | Dense embeddings, approximate nearest neighbor | /retrieve, /query |
| Graph enrichment | Entity linking + neighborhood expansion | /retrieve, /query (when enabled) |
| Ontology context | Approved entity/relationship summary in LLM prompt | /query |
| Deterministic lookup | Record ID and aggregation heuristics | /query (database fabrics) |

Vector search remains the primary recall path. Graph and ontology layers reduce ambiguity in schema-heavy domains.

---

## 2. Embedding Stack

| Component | Specification |
|-----------|---------------|
| Framework | sentence-transformers |
| Model | all-MiniLM-L6-v2 |
| Dimension | 384 |
| Vector store | ChromaDB 0.4.x |
| Distance | Chroma default (converted to similarity score as 1 - distance) |

Embeddings are computed at fabric ingest time via `vector_service.create_embeddings` and stored in the documents collection.

---

## 3. Vector Service

Module: `backend/app/services/vector_service.py`

| Operation | Description |
|-----------|-------------|
| add_documents | Batch embed and upsert chunks for fabric_id |
| search_similar_chunks | Top-k cosine similarity with optional source_id filter |
| search_documents | General search with threshold |
| get_source_documents | Retrieve indexed content for graph reconstruction |

Chroma persistence directory is configurable via `KF_CHROMA_DIR`.

---

## 4. Retrieval Orchestrator

Module: `backend/app/services/retrieval/retrieval_orchestrator.py`

### 4.1 Pipeline stages

```text
1. Vector search (Chroma, top-k clamped 1–25)
2. Entity linking (token match against graph node labels)
3. Graph expansion (1–2 hops via graph_store.get_neighbors)
4. Context merge (prepend graph summary chunk)
5. Ontology summary injection (for /query path)
```

### 4.2 Configuration

| Variable | Default | Effect |
|----------|---------|--------|
| USE_GRAPH_RETRIEVAL | false (true in Docker Compose example) | Global graph enrichment toggle |
| use_graph (request body) | inherits global | Per-request override on /retrieve |

### 4.3 Response envelope extension

`/retrieve` returns:

- chunks (ranked)
- graph_context (nodes, edges, paths)
- entities (linked node list)
- ontology_version_id
- retrieval_trace (stage diagnostics)

---

## 5. Query and LLM Synthesis

### 5.1 Endpoint

`POST /api/v1/knowledge/query/{fabric_id}`

### 5.2 LLM providers

| Provider | Configuration |
|----------|---------------|
| OpenAI | OPENAI_API_KEY, DEFAULT_LLM_PROVIDER=openai |
| Anthropic | ANTHROPIC_API_KEY |
| Google Gemini | GEMINI_API_KEY |

Provider selection via request body `llm_provider` where supported.

### 5.3 BYOK (Bring Your Own Key)

External callers authenticated via inbound API key must supply `X-LLM-API-Key` for `/query`. Local development callers may use server-configured keys.

`/retrieve` does not invoke an LLM and does not require BYOK.

### 5.4 Context assembly

For database fabrics, `RetrievalOrchestrator` replaces raw vector-only fetch. Composite fabrics merge multi-source results. PDF fabrics use upload directory reads as fallback when vector results are sparse.

Deterministic paths handle:

- Duplicate count queries
- Record ID lookups
- Aggregation patterns (top N, highest value)

---

## 6. Ontology-Aware Prompting

On `/query`, ontology summary is built from approved version:

- Up to 12 class names
- Up to 8 relationship names

Injected into LLM system context via `build_query_context`.

---

## 7. Exploratory vs Canonical in Retrieval

| Graph type | Used in retrieval |
|------------|-------------------|
| Canonical (PostgreSQL) | Yes, when approved version exists |
| Exploratory (co-occurrence) | No — UI only |

---

## 8. Machine Learning Training

Optional fabric training pipeline:

| Component | Technology |
|-----------|------------|
| training_service | Custom training orchestration |
| Models | XGBoost, scikit-learn, transformers (domain-dependent) |
| Storage | backend/models/ |

Training is orthogonal to retrieval embeddings; fine-tuned models support classification endpoints under `/api/v1/knowledge/models/`.

---

## 9. Ontology Discovery LLM

| Setting | Default |
|---------|---------|
| ONTOLOGY_LLM_MODEL | gpt-4 |
| ONTOLOGY_LLM_TEMPERATURE | 0.2 |
| ONTOLOGY_MAX_CHUNKS_FOR_LLM | 10 |

Schema analyzer and document pipeline use structured JSON output parsing with retry logic.

---

## 10. Performance Considerations

| Stage | Typical latency driver |
|-------|------------------------|
| Embedding search | Chroma index size, top_k |
| Graph expansion | Edge count, hop depth |
| LLM synthesis | Provider API, context token count |

Recommended starting limits:

- top_k: 5 for query, 5–10 for retrieve
- graph hops: 1–2
- chunk token budget: managed in context merge (future explicit cap)

---

## 11. Evaluation (Roadmap)

Golden eval datasets planned under `backend/tests/golden/` with CI regression gates (Phase 5 of production roadmap). Metrics: entity recall, grounding score, graph path presence.

---

## 12. Next Document

See [07-api-and-integration.md](./07-api-and-integration.md) for complete API reference patterns.
