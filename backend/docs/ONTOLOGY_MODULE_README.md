# Ontology Discovery Module

This document describes the **Ontology Discovery** (Ontology Studio) feature added to the Knowledge Fabric application.

## Overview

The Ontology module ingests customer-provided **PDF** and **XML** files (from the existing upload repository), runs a pipeline to extract semantic candidates, classifies them into **entities**, **relationships**, **attributes**, **business rules**, and **constraints**, and presents a reviewable ontology model. The output can be used for canonical data modeling, knowledge graph generation, and AI-agent context grounding.

## File and Folder Structure

### Backend (added or modified)

```
backend/
├── app/
│   ├── core/
│   │   └── config.py                    # + .xml in ALLOWED_EXTENSIONS, ONTOLOGY_* settings
│   ├── models/
│   │   └── ontology.py                  # NEW: OntologyProject, OntologyVersion, OntologyClass, etc.
│   ├── schemas/
│   │   └── ontology.py                 # NEW: Request/response DTOs
│   ├── api/v1/
│   │   ├── api.py                      # + ontology router
│   │   └── endpoints/
│   │       └── ontology.py             # NEW: Ontology REST endpoints
│   └── services/
│       └── ontology/
│           ├── __init__.py
│           ├── artifact_loader.py      # Load PDF/XML from upload repo
│           ├── pdf_processor.py        # PDF text + section/heading extraction
│           ├── xml_processor.py        # XML tag hierarchy, leaf/parent
│           ├── semantic_chunker.py     # Chunk text for LLM
│           ├── concept_extractor.py    # Rule-based entity/rel/attr/rule extraction
│           ├── ontology_classifier.py  # Merge + classify candidates
│           ├── relation_inference_engine.py  # Infer source/target for relationships
│           ├── attribute_mapper.py      # Map attributes to classes
│           ├── ontology_assembler.py    # Build OntologyVersion from pipeline output
│           ├── ontology_validator.py   # Referential integrity checks
│           ├── ontology_persistence_service.py  # File-based projects/versions/runs
│           ├── ontology_export_service.py      # JSON / CSV / graph / canonical export
│           ├── llm_ontology_service.py  # LLM-assisted extraction (OpenAI)
│           └── discovery_orchestrator.py       # Full pipeline orchestration
├── tests/
│   ├── __init__.py
│   ├── fixtures/
│   │   └── sample_ontology.xml         # Sample XML for tests
│   └── test_ontology_pipeline.py      # Unit tests for pipeline
└── docs/
    └── ONTOLOGY_MODULE_README.md       # This file
```

### Frontend (added or modified)

```
frontend/src/
├── App.tsx                             # + routes /ontology, /ontology/workspace/:projectId
├── components/
│   └── Layout.tsx                     # + "Ontology Discovery" nav item
├── utils/
│   └── ontologyApi.ts                 # NEW: ontology API client
└── pages/
    └── ontology/
        ├── OntologyDashboard.tsx      # Project list, create project
        └── OntologyWorkspace.tsx      # Source artifacts, run discovery, review, export
```

## Key Components

| Component | Role |
|-----------|------|
| **ArtifactLoader** | Resolves file names/paths from upload repo to `SourceArtifact` list (PDF/XML only). |
| **PDFProcessor** | Extracts full text and section/heading blocks; produces evidence with page numbers. |
| **XMLProcessor** | Parses XML, builds node hierarchy (path, tag, is_leaf), finds repeated groups. |
| **SemanticChunker** | Splits text into LLM-sized chunks with paragraph-boundary awareness. |
| **ConceptExtractor** | Rule-based: nouns → entities, verbs → relationships, labels → attributes, must/required → rules. XML: parent → entity, leaf → attribute. |
| **OntologyClassifier** | Merges rule-based + LLM candidates, dedupes by normalized name, boosts confidence by repetition. |
| **RelationInferenceEngine** | Binds relationship names to (source_entity, target_entity) using co-occurrence in text. |
| **AttributeMapper** | Assigns each attribute to a class (by XML parent path or snippet context). |
| **OntologyAssembler** | Builds `OntologyVersion` (classes, relationships, attributes, constraints) with evidence. |
| **OntologyValidator** | Checks class_id / source_class_id / target_class_id referential integrity. |
| **OntologyPersistenceService** | Saves/loads projects (JSON), versions (per-file JSON), runs (JSON). |
| **OntologyExportService** | Exports version as JSON, CSV, graph schema, and canonical model. |
| **LLMOntologyService** | Calls OpenAI with a structured prompt; parses and normalizes JSON (entities, relationships, attributes, business_rules). |
| **DiscoveryOrchestrator** | Runs the full pipeline in a background thread; updates run status and saves the resulting version. |

## Setup

- **Backend**: No new pip dependencies beyond existing (`PyPDF2`, `pydantic`, `openai`). Config uses `ALLOWED_EXTENSIONS` including `.xml` and optional env vars for `ONTOLOGY_DATA_DIR`, `ONTOLOGY_LLM_MODEL`, etc.
- **Frontend**: No new npm dependencies; uses existing routing and design (Tailwind, Heroicons).
- **Upload**: Ensure PDF/XML files are uploaded via the existing Upload/Knowledge flow so they appear under `GET /api/v1/ontology/artifacts/available`.

## API Endpoints (summary)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/ontology/projects` | Create project |
| GET | `/api/v1/ontology/projects` | List projects |
| GET | `/api/v1/ontology/projects/{projectId}` | Get project |
| GET | `/api/v1/ontology/artifacts/available` | List PDF/XML in upload repo |
| POST | `/api/v1/ontology/projects/{projectId}/discover` | Start discovery (body: `artifact_ids`, `use_llm`) |
| GET | `/api/v1/ontology/projects/{projectId}/runs/{runId}` | Get run status |
| GET | `/api/v1/ontology/projects/{projectId}/versions` | List versions |
| GET | `/api/v1/ontology/projects/{projectId}/versions/{versionId}` | Get version (classes, relationships, attributes, constraints) |
| PUT | `/api/v1/ontology/classes/{id}` | Update class |
| PUT | `/api/v1/ontology/relationships/{id}` | Update relationship |
| PUT | `/api/v1/ontology/attributes/{id}` | Update attribute |
| POST | `/api/v1/ontology/review/approve` | Approve elements |
| POST | `/api/v1/ontology/review/reject` | Reject elements |
| POST | `/api/v1/ontology/merge` | Merge entities |
| GET | `/api/v1/ontology/export/{versionId}?format=json|csv|graph` | Export |
| GET | `/api/v1/ontology/export/{versionId}/canonical` | Canonical model |

## Example API Payloads

**Start discovery**

```json
POST /api/v1/ontology/projects/proj_abc/discover
{
  "artifact_ids": ["document.pdf", "schema.xml"],
  "use_llm": true
}

Response: { "success": true, "data": { "run_id": "run_xyz", "project_id": "proj_abc", "status": "queued" } }
```

**Get version (excerpt)**

```json
GET /api/v1/ontology/projects/proj_abc/versions/ver_xyz

Response: {
  "success": true,
  "data": {
    "id": "ver_xyz",
    "classes": [
      { "id": "cls_1", "name": "Claim", "normalized_name": "Claim", "confidence_score": 0.85, "status": "draft", "source_evidence": [...] }
    ],
    "relationships": [
      { "id": "rel_1", "source_class_id": "cls_1", "relationship_name": "has", "target_class_id": "cls_2", "confidence_score": 0.7 }
    ],
    "attributes": [
      { "id": "attr_1", "class_id": "cls_1", "attribute_name": "claim_id", "normalized_name": "Claim Id", "data_type_guess": "string" }
    ]
  }
}
```

## Sample Ontology JSON Output (from sample XML fixture)

Running discovery on a small XML like:

```xml
<Root>
  <Claim><claim_id>string</claim_id><policy_number>string</policy_number></Claim>
  <Policy><policy_id>string</policy_id></Policy>
</Root>
```

would produce an export JSON similar to:

```json
{
  "version_id": "ver_...",
  "project_id": "proj_...",
  "version_label": "draft",
  "is_draft": true,
  "entities": [
    { "id": "cls_...", "name": "Claim", "normalized_name": "Claim", "definition": null, "confidence_score": 0.9, "status": "draft" },
    { "id": "cls_...", "name": "Policy", "normalized_name": "Policy", "definition": null, "confidence_score": 0.85, "status": "draft" }
  ],
  "relationships": [],
  "attributes": [
    { "id": "attr_...", "class_id": "cls_...", "attribute_name": "claim_id", "normalized_name": "Claim Id", "data_type_guess": null, "required_flag_guess": false, "confidence_score": 0.75 },
    { "id": "attr_...", "class_id": "cls_...", "attribute_name": "policy_number", "normalized_name": "Policy Number", "confidence_score": 0.75 },
    { "id": "attr_...", "class_id": "cls_...", "attribute_name": "policy_id", "normalized_name": "Policy Id", "confidence_score": 0.75 }
  ],
  "constraints": []
}
```

(Exact IDs and scores depend on the run.)

## Extensibility

The code is structured so you can later add:

- Ontology alignment with FHIR / SNOMED / ACORD (e.g. `OntologyMapping` and alignment service).
- Ontology merge across projects.
- Ontology-to-knowledge-graph automatic generation (use `export?format=graph` as input).
- Ontology-driven RAG chunk enrichment and agent context injection.
- Ontology drift detection on newly uploaded files.

## Running Tests

From the backend directory:

```bash
pip install pytest
pytest tests/test_ontology_pipeline.py -v
```
