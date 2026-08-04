# Weave durable fix: full-fabric retrieve must not stop at 5,000 chunks

**Status:** Implemented in Knowledge-Fabric (local Docker bind-mount; uvicorn reload applied).  
**Symptom:** Weave Chat InChIKey validity reported **5,000** rows while the fabric had **76,329**.

## Root cause

1. `list_source_chunks(source_id)` defaulted to **limit=5000**.
2. Analytics row load used `get_source_documents` without paging.

## Fix

1. `list_source_chunks(..., limit=0)` — uncapped; pages Chroma in 5k batches.
2. Full-fabric call sites pass `limit=0`.
3. `_load_fabric_row_documents` uses uncapped `list_source_chunks`.
4. `analyze_inchikey_validity` — server-side valid / invalid / blank counts.

## Verify

Ask: `How many invalid InChIKeys were rejected?`

Expect total ≈ fabric size (e.g. **76,329**), intent `inchikey_format_validity`.

Use Weave Chat **0.1.5+** (prefers Weave `/query` for this question).
