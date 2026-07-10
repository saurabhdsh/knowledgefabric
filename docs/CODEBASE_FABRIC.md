# Codebase / Workspace Knowledge Fabric

Create a knowledge fabric from a **zip**, **folder**, or **git repository**, with structural analysis, LLM enrichment (Bedrock/OpenAI), a typed code graph, and a downloadable **migration JSON**.

---

## Inputs

| Mode | How |
|------|-----|
| **Zip** | Upload a `.zip` of the workspace |
| **Folder** | Browser packs the folder into a zip (JSZip) then uploads |
| **Git** | Server clones the repo — **public**, **PAT**, or **SSH private key** |

Credentials are used only for clone, kept ephemerally on the analysis job, then scrubbed. They are **never** written into the fabric payload or migration JSON.

---

## Create (UI)

1. Sign in (admin or user with **Create Knowledge**)
2. **Create Knowledge** → **Codebase / Workspace**
3. Choose zip / folder / git, set name + optional migration goal
4. Wait for progress (inventory → graph → enrichment → blueprint → index)
5. Opens the knowledge graph with discovery summary + migration waves

---

## Fabrics actions

For `source_type=codebase`:

- **View** → knowledge graph
- **Download** → full migration JSON (`weave.codebase.migration/v1`)
- **Re-analyze** → re-run pipeline on staged workspace (optionally re-clone git)

You can also **import** a migration JSON from the Codebase create dialog.

---

## Bedrock / OpenAI

Enrichment and blueprint refinement use the existing LLM router:

- Default provider from `DEFAULT_LLM_PROVIDER` (e.g. `bedrock`)
- Falls back to OpenAI if configured
- Only top modules are sent to the LLM (not the whole repo)

Same `.env` as other Weave LLM features — no extra keys for codebase.

---

## Docker / EC2

- Backend image must include **`git`** and **`openssh-client`** (updated `backend/Dockerfile`)
- Ensure enough disk under `uploads/codebase/` for clones
- Job worker must be enabled (`ENABLE_JOB_WORKER`, default on)

---

## Limits (defaults)

- Max uncompressed zip ~400 MB / 25k entries
- Skips `node_modules`, `.git`, `venv`, binaries, etc. (+ `.gitignore`)
- Parse cap ~2500 source files for structural graph

---

## API (summary)

| Method | Path |
|--------|------|
| `POST` | `/api/v1/knowledge/create-codebase-fabric` (multipart) |
| `GET` | `/api/v1/knowledge/progress/{progress_id}` |
| `POST` | `/api/v1/knowledge/{id}/codebase/reanalyze` |
| `GET` | `/api/v1/knowledge/{id}/migration-export` |
| `POST` | `/api/v1/knowledge/import-codebase-migration` |
