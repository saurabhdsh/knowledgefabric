# Weave Knowledge Fabric — Release 2.0

Release 2.0 changes how a Knowledge Fabric is created. In 1.x every source
(PDF, database, composite) was turned into text chunks, stored, and at question
time the whole fabric was put into the prompt. 2.0 replaces that with one staged
pipeline in which every inference carries evidence and a measured confidence,
and every fabric gets a quality report at creation.

This document holds the review that motivated the release, the full roadmap
(Phases 0–5), and the status of each phase.

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Fix what is wrong today | **Done (local)** |
| 1 | One staged pipeline for all sources | **Done (local)** |
| 2 | Evidence-based semantic layer | **Done (local)** |
| 3 | Composite as a real join | **Done (local)** |
| 4 | Retrieval and measurement | **Done (local)** |
| 5 | Enterprise operations | **Done (local)** |

---

## 1. Review of the 1.x creation logic

Findings, most serious first. File references are to the 1.x code.

1. **Vector search was not semantic and broke on every restart.**
   The real embedding model was off by default (`ENABLE_TRANSFORMER_EMBEDDINGS`
   unset), so embeddings were a 64-slot word-count hash
   (`vector_service.create_embeddings`). The hash used Python's built-in
   `hash()`, which is seeded per process, so after a backend restart question
   vectors no longer matched stored vectors. This was hidden because the default
   query mode retrieved the entire fabric.
2. **Database fabrics were a capped sample presented as the full picture.**
   MongoDB, Databricks and Snowflake default to 1,000 rows per collection or
   table. The model was told the analytics snapshot was "FULL FABRIC —
   authoritative", with a fixed 0.98 confidence.
3. **PDF ingestion lost structure and could pick the wrong files.**
   - Text came from `PyPDF2` with fixed 1,000-character cuts, no tables, no OCR.
   - The stored "page number" was the chunk index, so citations were wrong.
   - `create-pdf-fabric` took the N most recently uploaded files in the shared
     upload folder, not the files named in the request, so two concurrent users
     could get each other's documents.
   - A failed extraction or indexing still produced an "active" fabric.
4. **Composite was a copy, not a join.**
   - It copied chunks from the source fabrics once and never refreshed.
   - Nothing linked a person in a PDF to their database row.
   - No ontology job ran for it.
   - It lost the exact-count path, which only ran for `source_type == "database"`.
   - Its graph fell back to word co-occurrence.
5. **The ontology was built from a thin slice.**
   - Live MongoDB fabrics got no schema profile, so discovery read only the
     first 300 row chunks.
   - The LLM saw only the first 10 chunks.
   - Foreign keys were guessed from the `_id` suffix, not from the values.
   - Relationship direction was whichever two entity names were found first.
6. **The stored graph held only entity types, not instances.** The instance
   view was rebuilt on every page load from domain-specific column rules in
   `knowledge.py`. Graph context reached retrieval only after an ontology
   version was approved, and then only as lines like "Relationship: has_claim".
7. **"Training" was simulated.** It slept for 10 seconds and wrote placeholder
   files; composite fabrics were hardcoded to "trained". Query confidence was a
   set of constants.

Kept from 1.x: the exact-count analytics engine, the job queue, ontology
versioning with approval, and LLM provider routing.

---

## 2. Roadmap

### Phase 0 — Fix what is wrong today

- Turn on a real embedding model by default, record the model and version per
  fabric, and re-index existing fabrics.
- Bind PDF fabrics to the files named in the request.
- Mark a fabric failed when extraction or indexing fails.
- Show rows imported against rows in the source.
- Remove or relabel the simulated training.

### Phase 1 — One staged pipeline for all sources

- Stages are Profile → Parse → Model → Index → Validate → Publish, run as a
  job with a saved manifest.
- Database profiling covers types, null rates, key candidates, and foreign
  keys detected by value overlap.
- PDF parsing becomes layout-aware: headings, tables, real page numbers, OCR
  for scans.
- Rows live in a queryable table store and aggregates are answered by queries;
  only text and entity summaries are embedded.

### Phase 2 — Evidence-based semantic layer

- Build the ontology from the full profile.
- Give every relationship a source, a target, evidence and a measured
  confidence.
- Persist the instance-level graph.
- Move domain rules out of the endpoint into configurable domain packs.

### Phase 3 — Composite as a real join

- Resolve entities across sources, so a person named in a care-plan PDF links
  to their member row.
- Use one shared ontology across the sources.
- Route count questions to the table store, narrative questions to documents,
  and mixed questions to both.
- Reference the sources live, with refresh.

### Phase 4 — Retrieval and measurement

- Replace retrieve-everything with keyword plus vector search, a reranker and
  a token budget.
- Make graph expansion return actual facts.
- Keep a golden question set per fabric and measure retrieval recall and
  answer groundedness.
- Compute confidence from those measurements.

### Phase 5 — Enterprise operations

- Incremental sync, fabric versioning and lineage, per-fabric index isolation,
  PII classification, access control and audit.

---

## 3. Implementation status

**Phases 0–5 are implemented and pushed (November 2026, `0221ce4` and follow-ups).**
EC2 still needs an image rebuild and a re-index after deploy.

### Phase 0 — done

| Item | Status |
| --- | --- |
| Real embedding model on by default | Done — ONNX `all-MiniLM-L6-v2` (384-d), collection `kf_onnx-all-MiniLM-L6-v2` |
| Model + version recorded per fabric | Done — `fabric["embedding"]` stamp |
| Existing fabrics re-indexed | Done locally — 10 fabrics, 88,515 chunks, 0 failures |
| PDF fabrics bound to named uploads | Done — `upload_registry` + `stored_name`; unknown names return 404 |
| Failed status on extraction/index failure | Done — fabric `status=failed`, `model_status=failed`, stage in error |
| Rows imported vs rows in source | Done — on fabric + connection_info; Mongo/SQL count the source |
| Simulated training removed | Done on PDF / database / CSV / composite / Cost-of-Care / reference-flow paths; `model_status` is `indexed` |

### Phase 1 — done

| Item | Status |
| --- | --- |
| Staged pipeline + saved manifest | Done — Profile → Parse → Model → Index → Validate → Publish; `GET /knowledge/{id}/manifest` |
| DB profiling (types, nulls, keys, FKs by overlap) | Done — verified 11 tables / 15 FKs on Cost of Care CSVs |
| Queryable table store + SQL aggregates | Done — per-fabric SQLite, text-to-SQL, entity lookup |
| Only text + entity summaries embedded | Done — no raw row chunks for v2 tabular fabrics |
| Layout-aware PDF parsing + OCR | Done — pdfplumber headings/tables/real pages; Tesseract OCR for scans |
| Structure-aware chunking + citations | Done — section path + page range on citations |
| Composite through the same pipeline | Done — merges table stores, discovers cross-source FKs, prefixes origins |

### Phase 2 — done

| Item | Status |
| --- | --- |
| Ontology from the full measured profile | Done — `schema_analyzer.build_profile_from_fabric` loads table-store profile (`source=data_profile`); measured FKs skip LLM merge |
| Relationship source, target, evidence, confidence | Done — profile → bind → assemble → graph edges keep snippet, overlap basis, cardinality, column bindings |
| Persist instance-level graph | Done — `instance_materialization_service` writes sampled instances + FK edges on graph build (`INSTANCE_GRAPH_PER_TABLE_LIMIT`, default 20) |
| Domain packs (rules out of endpoint) | Done — `domain_packs/` (`healthcare_cost_of_care`, `itsm_servicenow`); knowledge helpers delegate |

### Phase 3 — done

| Item | Status |
| --- | --- |
| Cross-source entity resolution (PDF ↔ row) | Done — `entity_resolution.link_document_chunks` stamps `linked_entities_json` on doc chunks and persists `data/fabric_entity_links/{id}.json` |
| One shared ontology across sources | Done — `composite_ontology.choose_shared_ontology_project` reuses a shared / approved source project; discovery still runs on the merged profile |
| Route SQL vs docs vs mixed | Done — `classify_query_intent` → `sql` / retrieval / `hybrid` (SQL + passages + linked rows) |
| Live source reference + refresh | Done — `POST /knowledge/{id}/refresh-composite` full rebuild from current sources; `GET .../entity-links` |

### Phase 4 — done

| Item | Status |
| --- | --- |
| Keyword + vector + rerank, not retrieve-everything | Done — `QUERY_RETRIEVE_ALL` defaults off; `hybrid_ranker.fuse_and_rerank` |
| Token budget | Done — `QUERY_TOKEN_BUDGET_CHARS` (default 12,000) packs evidence |
| Graph expansion returns facts | Done — neighbor properties + `graph_facts` (values, confidence), not type-only lines |
| Golden set + recall / groundedness | Done — `tests/golden/cost_of_care.json`, `score_golden_item` |
| Confidence from measurements | Done — rerank, token recall, keyword hit, graph facts, SQL backing |

### Phase 5 — done

| Item | Status |
| --- | --- |
| Fabric versioning and lineage | Done — `on_publish` appends `data/fabric_lineage/{id}.json`; `GET /knowledge/{id}/lineage` |
| Incremental sync | Done — primary-key diff; column change forces full rebuild; `POST /knowledge/{id}/sync-rows` applies the delta |
| Per-fabric index isolation | Done — `ISOLATE_FABRIC_INDEX` (default on); collection `kf_f_{hash}`; legacy shared collections still readable |
| PII classification | Done — domain-pack keywords plus name patterns; stamped on publish; `GET /knowledge/{id}/pii` |
| Access control and audit | Done — owner / analyst / viewer; viewers cannot export or sync; query and grants write `data/fabric_audit/events.jsonl` |

### Verified (local Docker, live API)

- Isolated unit suite: **41/41** `test_fabric_pipeline_v2.py` + **6/6**
  `test_phase2_semantic_layer.py` + **3/3** `test_phase3_composite.py`
  (**50 passed** together) + platform graph tests.
- Cost of Care CSV fabric: 3,224 rows / 11 tables / 15 FKs; SQL answered
  “520 members”; entity + exact-token routes for Lisa Chen / `MEM-LISA-COPD`.
- Profiled knowledge graph: 208 nodes, 495 edges from measured FKs.
- Phase 2 live on e2e CoC fabric: ontology from `data_profile` (11 classes /
  15 relationships, all with evidence + cardinality + columns); graph build
  persisted **196 instances** (incl. Lisa Chen) + class graph; every stored
  edge carries `evidence_refs`.
- Phase 3 live on `fabric_composite_1794630522_3f405f17` (CoC + Care Policy):
  **172** document→row entity links; `sql` / `narrative` / `hybrid` routes
  verified; refresh kept fabric id and re-linked; `GET .../entity-links` OK.
- Text PDF: page/section citations (`Care Policy.pdf, p. 2, … > 2 Cost Benchmarks`).
- Scanned PDF: `pages_ocr=1`, answer cited the OCR’d 48-hour follow-up.
- Composite (CSV + policy): policy citation prefixed with origin; SQL
  `MEM-LISA-COPD has 10 claims`.
- Unknown upload name → 404 `Not uploaded: …`.
- Legacy re-indexed fabric still answers analytically.

### Not migrated / still 1.x behaviour

- A live ServiceNow instance API is not called. File upload, the incident
  reference set, and the connection sample all run through the staged tabular
  pipeline (profile, table store, measured keys, `indexed`).
- Codebase analysis indexes real embeddings, marks `model_status=indexed`, and
  stamps lineage on completion. It does not build a SQL table store, because a
  repository is not a relational source.
- Legacy database fabrics created before 2.0 have no table store until re-created.
  Their existing vectors stay in the shared collection until re-indexed; new
  writes use the per-fabric collection.

### EC2 upgrade steps

1. Rebuild and redeploy the backend image (OCR, pdfplumber, baked ONNX model).
2. Restart the API so it loads the new collection.
3. Run `python -m app.tools.reindex_embeddings` (or
   `POST /api/v1/knowledge/reindex-embeddings`) against the live fabrics.
4. Recreate any database/CSV fabrics that need the table store and SQL path.
