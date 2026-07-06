# Scaling Ontology Discovery for High Volume (Millions of Records)

When you have **millions of image-sized (or large) records**, running ontology discovery on every artifact in one go is not feasible: it would exhaust memory, time out, and be costly for LLM calls. Use the following approach.

---

## 1. **Cap artifacts and chunks per run (recommended first step)**

- **Limit how many artifacts** are processed in a single discovery run.
- **Limit how many text chunks** are used for classification and for LLM, so memory and API cost stay bounded.

### Configuration (backend)

Set in `.env` or `backend` config:

```env
# Process at most N artifacts per discovery run (0 = no limit)
ONTOLOGY_MAX_ARTIFACTS_PER_RUN=200

# Use at most N text chunks for classification/relations (0 = no limit)
ONTOLOGY_MAX_CHUNKS_TOTAL=2000

# Send at most N chunks to the LLM per run (cost/latency)
ONTOLOGY_MAX_CHUNKS_FOR_LLM=20
```

### Per-request overrides (API)

When starting discovery you can override these for that run only:

```json
POST /api/v1/ontology/projects/{project_id}/discover
{
  "artifact_ids": ["file1.png", "file2.jpg", ...],
  "use_llm": true,
  "max_artifacts_per_run": 100,
  "max_chunks_for_llm": 15
}
```

- If `max_artifacts_per_run` is set (config or request), only the **first N** artifacts are processed in that run.
- `max_chunks_total` caps the total chunks used for rule extraction + classification + relation inference.
- `max_chunks_for_llm` caps how many chunks are sent to the LLM in that run.

Use these so each run stays within acceptable memory and time (e.g. 100–500 artifacts, 500–2000 chunks, 10–30 LLM chunks).

---

## 2. **Batch discovery: many runs, then merge**

- Split your **full catalog into batches** (e.g. by file list, folder, or time window).
- Run **one discovery run per batch**, each with a cap (e.g. `max_artifacts_per_run=200`).
- You get **one ontology version per run**.
- **Merge** results in a separate step:
  - Manually or via a script: merge entities/relationships/attributes from multiple versions (dedupe by normalized name or id), then save a single “canonical” version; or
  - Use a future “merge versions” API if the product adds it.

So the method is: **batch the inputs → run discovery per batch → merge the resulting ontologies**.

---

## 3. **Sampling for very large catalogs**

- For **millions** of records, you often don’t need to process all of them to get a stable ontology.
- **Sample** a representative subset (e.g. 1–5% or 10k–50k artifacts) and run discovery on that.
- Options:
  - **Random sample** of `artifact_ids` before calling discover.
  - **Stratified**: e.g. by source type (PDF vs image), date range, or domain, then sample from each stratum.
- Pass only the sampled `artifact_ids` into the discover API (with the caps above so each run is still bounded).

This gives you **one entity/relationship model** that is representative of the full volume without processing every record.

---

## 4. **Incremental / append discovery (future)**

- Today each run produces a **new version** from scratch for the artifacts in that run.
- A possible extension is **incremental discovery**: new runs would **add** entities/relationships to an existing version (merge new evidence, dedupe), instead of rebuilding from zero.
- Until that exists, batching + merging (section 2) is the way to simulate “incremental” at scale.

---

## 5. **Operational tips**

- **Images**: Each image is OCR’d (or processed) and turned into text chunks. Many small images → many chunks. Use `ONTOLOGY_MAX_ARTIFACTS_PER_RUN` and `ONTOLOGY_MAX_CHUNKS_TOTAL` to keep a single run manageable.
- **Queue/workers**: Discovery runs in a background thread. For very large catalogs, run multiple batches (e.g. sequential or via an external job queue) and merge results.
- **Monitoring**: Use run status and logs (`current_stage`, `progress_percent`, `run_logs`) to see how far each run got and whether you hit limits (e.g. “Limiting to first 200 of 50000 artifacts”).

---

## Summary

| Goal | Method |
|------|--------|
| Keep a single run bounded | Set `ONTOLOGY_MAX_ARTIFACTS_PER_RUN`, `ONTOLOGY_MAX_CHUNKS_TOTAL`, `ONTOLOGY_MAX_CHUNKS_FOR_LLM` (config or request). |
| Process millions in chunks | Split catalog into batches; run discovery per batch; merge resulting ontologies. |
| Avoid processing everything | Sample a representative subset of artifacts; run discovery on the sample. |
| Control cost/latency | Lower `ONTOLOGY_MAX_CHUNKS_FOR_LLM` (and optionally `use_llm=false` for rule-only runs). |

Using these, ontology discovery can be used effectively even when the source is millions of image-sized (or large) records.
