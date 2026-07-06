# Enhancement: Universal Schema Understanding for Ontology Discovery

> **Status:** Proposed — not implemented
> **Owner:** TBD
> **Priority:** High — addresses a recurring user-reported gap
> **Last updated:** 2026-05-25

---

## 1. Problem Statement

Ontology Discovery should produce a coherent set of **entities, relationships,
and attributes** regardless of which data source built the Knowledge Fabric
(Databricks, Snowflake, MongoDB, PostgreSQL, MySQL, SQLite, CSV upload,
ServiceNow, etc.) **and regardless of the schema's naming convention**.

Today, the system relies primarily on pattern-matching rules over column
names. Each time a new naming convention is encountered (data-warehouse
suffixes, ITSM prefix-groups, ServiceNow `sys_*`, ERP 5-char codes, etc.)
we extend the rules. That is **reactive**, and it's the wrong long-term
shape for a self-service product.

User feedback (paraphrased): "Whatever data we are creating the fabric on,
the ontology and all should be handled on its own."

This document defines what "on its own" actually requires and proposes the
architecture to get there.

---

## 2. Current State (Summary)

| Layer | Implementation today | Notes |
|---|---|---|
| Rule-based column classification | ✅ `concept_extractor.py` | Handles `*_id`, `*Dim/*Fact/*Bridge/*Lookup/*Mapping`, CamelCase nouns, snake_case prefix groups, `related_*`, `_number`/`_no`/`_pk` primary keys, and ITSM/healthcare priority entities. Case-insensitive across CamelCase / SCREAMING_SNAKE / snake_case / camelCase / kebab-case. |
| LLM extraction over chunks | ✅ `LLMOntologyService.extract_from_chunk` | Runs on first ~10 chunks of vectorized text. Sees fragments, not the full schema. |
| Statistical / value-pattern analysis | ❌ Not implemented | Never look at value distributions, uniqueness, or regex signatures. |
| Schema-aware LLM analysis | ❌ Not implemented | LLM is never given the column list + sample rows as a single coherent prompt. |
| Self-improvement loop (human edits → few-shot) | ❌ Not implemented | Review edits via `/api/v1/ontology/classes/{id}` PUT are not fed back into discovery. |

**Result:** rules get the platform 70–80 % of the way for any new schema; the
last 20 % requires either a developer to extend rules, or a human to clean up
the ontology via the review UI.

---

## 3. Why Rules Alone Will Never Be Enough

There is no upper bound on enterprise naming conventions. Examples we have
either already handled or that we will hit eventually:

| Domain | Convention examples |
|---|---|
| Healthcare | `mbr_*`, `clm_*`, `prov_*`, `dx_*`, `rx_*`, `MemberDim`, `ClaimFact` |
| Banking | `acct_*`, `txn_*`, `ctpy_*`, `instr_*`, `BIC`, `IBAN` |
| Insurance | `pol_*`, `quote_*`, `endorse_*`, `cov_*` |
| Manufacturing / SAP | `MATNR`, `KUNNR`, `VBELN`, `LIFNR`, custom `Z*`/`Y*` tables |
| Salesforce | `Account__c`, `Opportunity__c`, packaged `npsp__*` |
| Legacy AS/400 | 8-char abbreviations: `MEMNO`, `CLMHDR`, `PRVNPI` |
| ServiceNow | `sys_*`, `u_*`, `task_*`, `cmdb_ci_*` |
| ITSM (already handled) | `caller_*`, `service_*`, `ai_*`, `related_change`, `incident_number` |

A rules engine that "understands" all of these is impossible to ship and
unmaintainable. We need a layered approach where rules are the *last*
signal, not the first.

---

## 4. Target Architecture: Layered Schema Understanding

Three layers, in **execution order**:

```
┌───────────────────────────────────────────────────────────────┐
│  Layer 1 — Schema-aware LLM analysis (PRIMARY signal)         │
│  Input:   column list, types, sample values, table name, tags │
│  Output:  proposed entities, relationships, PKs, FKs, attrs   │
└───────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────┐
│  Layer 2 — Statistical / structural profiler (CORROBORATION)  │
│  Input:   column values from the actual fabric                │
│  Output:  cardinality, uniqueness, null %, top-K values,      │
│           value-pattern regex, candidate keys                 │
└───────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────┐
│  Layer 3 — Pattern rules (SANITY CHECK only)                  │
│  Input:   column names                                        │
│  Output:  classic *_id / DW-suffix / prefix-group hints       │
└───────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────┐
│  Reconcile + Confidence scoring + Persist                     │
│  Disagreements → "Review candidates" in existing review UI    │
└───────────────────────────────────────────────────────────────┘
```

### 4.1 Layer 1 — Schema-aware LLM analysis

New service: `SchemaUnderstandingService` (suggested path
`backend/app/services/ontology/schema_understanding_service.py`).

**Trigger:** automatically invoked during fabric creation (DB or CSV) and
during every Ontology Discovery run.

**Input to LLM (structured prompt):**

```json
{
  "fabric_name": "...",
  "source_type": "databricks|snowflake|mongodb|csv|...",
  "table_name": "...",
  "columns": [
    {
      "name": "...",
      "inferred_type": "string|int|float|datetime|json|...",
      "sample_values": ["..."],
      "value_pattern": "e.g. [A-Z]{3}\\d{6}",
      "null_percent": 0.0,
      "unique_percent": 0.0
    }
  ],
  "row_count": 0,
  "additional_context": "optional table docs / connector profile / tags"
}
```

**Required output (strict JSON, validated):**

```json
{
  "entities": [
    {
      "name": "Member",
      "primary_key_columns": ["member_id"],
      "description": "...",
      "confidence": 0.0
    }
  ],
  "relationships": [
    {
      "source": "Claim",
      "target": "Member",
      "via_column": "member_id",
      "name": "references_member",
      "cardinality": "many_to_one",
      "confidence": 0.0
    }
  ],
  "attributes": [
    {
      "column": "...",
      "owning_entity": "Member",
      "semantic_role": "id|name|date|code|amount|free_text|enum|...",
      "is_pii": false,
      "confidence": 0.0
    }
  ],
  "enumerations": [
    { "column": "...", "values": ["..."], "owning_entity": "..." }
  ]
}
```

**Design notes:**

- Only the schema + value patterns / samples are sent. Raw PHI / PCI values
  must be masked at the profiler step (see §4.2). This keeps the call
  HIPAA-safe.
- The prompt must include the *current ontology version* (if any) so the
  LLM proposes deltas, not duplicates.
- Use `temperature=0` and JSON-mode for reproducibility.
- Cache results keyed on a **schema fingerprint** (hash of `(column_names,
  inferred_types, value_pattern_signatures)`) so re-running discovery on
  the same shape is deterministic and instant.

### 4.2 Layer 2 — Statistical / structural profiler

New service: `SchemaProfiler` (suggested path
`backend/app/services/ontology/schema_profiler.py`).

For every column, compute:

- inferred type (with subtypes — `string<6>`, `int<positive>`, `datetime<iso>`, …)
- null %
- unique % / cardinality
- top-K most frequent values (K=10)
- value-pattern signature via regex generalization (e.g. `M\d{6}`)
- candidate-key score (`unique_percent` > 0.99 and `null_percent` < 1 %)
- candidate-enum score (`unique_count` < 50 and `null_percent` < 5 %)
- PII detector (email, SSN, phone, address, full-name patterns) → flag for masking

This output feeds Layer 1 and also gives the reconciler hard evidence to
veto/confirm LLM hypotheses.

### 4.3 Layer 3 — Pattern rules (existing `concept_extractor.py`)

Keep as-is but demote to a **sanity check**:

- If rule says "column X is an entity reference" but Layers 1+2 say
  "attribute," → mark `low_confidence`, do not override LLM unless layer 1
  also agrees.
- If rule says "column X is an attribute" but Layers 1+2 say "entity FK,"
  → trust LLM/profiler; log a "rule gap" entry for future tuning.

### 4.4 Reconciler

Combines outputs from all three layers into a single `OntologyVersion`
draft, attaching a per-element `evidence` block with:

```json
{
  "evidence_sources": ["llm_schema", "profiler", "rules"],
  "votes": { "llm_schema": 0.92, "profiler": 0.85, "rules": 0.70 },
  "final_confidence": 0.88,
  "disagreements": []
}
```

Disagreements become "Review candidates" in the existing ontology review
UI — the human edits become training signal (§4.5).

### 4.5 Self-improvement loop

Every time a reviewer edits an ontology element (`PUT /classes/{id}`,
`PUT /relationships/{id}`, `PUT /attributes/{id}`):

1. Record the change with the original LLM hypothesis and the
   reviewer's correction.
2. Store as a **few-shot example** in a per-tenant LLM example bank.
3. On the next discovery run, prepend the most relevant few-shot examples
   to the Layer-1 prompt.

Outcome: the system gets demonstrably better with use, per tenant, without
code changes.

---

## 5. Non-Functional Requirements

- **PII safety**: raw values for fields flagged PII by the profiler are
  *never* sent to the LLM — only patterns / masked samples.
- **Determinism**: schema-fingerprint cache; identical inputs produce
  identical outputs.
- **Latency budget**: schema-understanding step must complete in under
  ~10 seconds for tables up to 100 columns and 1M rows (profiler runs on
  a sampled subset of ≤ 50K rows).
- **Cost cap**: one LLM call per fabric per discovery run by default
  (cached afterwards).
- **Backwards compatibility**: existing ontologies must continue to load;
  the new fields (`evidence_sources`, `votes`) are additive.
- **Offline / on-prem mode**: if no LLM is available, fall back to Layer 2
  + Layer 3 only, with a banner in the UI explaining the degraded mode.

---

## 6. Affected Code

| Path | Change |
|---|---|
| `backend/app/services/ontology/schema_understanding_service.py` | **NEW** — LLM caller |
| `backend/app/services/ontology/schema_profiler.py` | **NEW** — statistical profiler |
| `backend/app/services/ontology/discovery_orchestrator.py` | Reorder pipeline so schema understanding runs *before* `concept_extractor.extract_from_tabular_row_chunks`; inject reconciler |
| `backend/app/services/ontology/concept_extractor.py` | Demote to sanity-check; keep rules but tag candidates with `source="rules"` |
| `backend/app/services/ontology/ontology_classifier.py` | Update to merge by `evidence_sources` rather than dedupe-by-name |
| `backend/app/models/ontology.py` | Extend `OntologyEvidence` to include `evidence_sources`, `votes`, `disagreements` |
| `backend/app/api/v1/endpoints/ontology.py` | Surface "Review candidates" from disagreements; record review edits as few-shot examples |
| `frontend/src/pages/ontology/*` | Show evidence sources + confidence per element; surface disagreements in the review UI |

---

## 7. Milestones

### Milestone 1 — Profiler MVP (no LLM)
- Implement `SchemaProfiler` with type inference, null %, uniqueness, value patterns.
- Wire into orchestrator. Use profiler output to improve Layer-3 rules
  (e.g. column with 99 % uniqueness becomes a key candidate even without
  `_id` suffix).
- **Exit criteria:** ≥ 10 % bump in entity / relationship recall on the
  ITSM + C-SNP fabrics with **no** code changes per dataset.

### Milestone 2 — Schema-aware LLM call (Layer 1)
- Implement `SchemaUnderstandingService` with strict JSON output.
- Schema fingerprint + cache.
- PII masking enforced via profiler.
- Add UI badges for confidence and evidence source.
- **Exit criteria:** new fabric from an unfamiliar schema (e.g. a SAP
  `MATNR`-style dataset) produces a usable ontology *with zero rule
  changes*.

### Milestone 3 — Reconciler + Review Candidates
- Combine layer outputs; surface disagreements in the existing review UI.
- Reviewer's resolutions persist as few-shot examples.
- **Exit criteria:** demonstrable lift in subsequent runs on the same
  tenant after ≥ 3 review-resolution cycles.

### Milestone 4 — Cross-table understanding
- Extend Layer 1 to accept *multiple* tables in one call so cross-table
  relationships (Member ↔ Claim ↔ Provider) are inferred jointly.
- Add database-introspection step where supported (Snowflake / Postgres
  / MySQL `INFORMATION_SCHEMA.KEY_COLUMN_USAGE`, Databricks `DESCRIBE
  TABLE EXTENDED`, MongoDB `$lookup`) to feed declared FKs directly into
  the relationship list.
- **Exit criteria:** fabric built across ≥ 5 tables produces a connected
  ontology graph with no orphan entities.

---

## 8. Acceptance Criteria (End-State)

A new fabric from **any** supported connector + **any** naming convention
must, with zero per-dataset code changes:

1. Pick a sensible **root entity** matching the row grain.
2. Surface **all** entities implied by the columns (FK columns, prefix
   groups, declared FKs, CamelCase nouns, etc.).
3. Produce **typed relationships** between those entities with cardinality
   when inferable.
4. Map every attribute to its owning entity (not just the root).
5. Identify candidate enumerations and primary keys.
6. Flag PII columns and respect masking before any external LLM call.
7. Cache the result by schema fingerprint and let humans correct any
   element with their corrections feeding back into the next run.

---

## 9. Open Questions

1. **Provider strategy** — single LLM provider (OpenAI) or pluggable
   (`ai_studio_service` already exists for this)? Recommendation: pluggable,
   with OpenAI as default and Gemini / Anthropic / on-prem (Ollama) as
   alternates.
2. **Sampling for profiler** — random sample, stratified sample, or first-N?
   Recommendation: stratified by `null_percent` + uniqueness, capped at 50K
   rows.
3. **Few-shot bank scope** — per-tenant, per-domain, or global? Recommendation:
   per-tenant with a curated global seed.
4. **Versioning of LLM prompt** — track prompt template versions in the
   ontology version metadata so we can replay/explain past runs.

---

## 10. Out of Scope (for now)

- Full join-graph discovery across heterogeneous data sources (a future
  enhancement; keep current intra-fabric scope for v1).
- Automatic SQL view generation from the discovered ontology (separate
  initiative).
- Real-time schema drift alerts (a separate observability work item).

---

## Appendix A — Why this came up

This document was created after a sequence of fabric discoveries surfaced
the same architectural gap on different shapes of data:

- **C-SNP star-schema** (`MemberDim`, `ClaimFact`, …) → rules updated to
  recognize DW suffixes and CamelCase nouns.
- **ITSM incident dataset** (`incident_number`, `caller_*`, `service_*`,
  `ai_*`, `related_*`) → rules updated to recognize first-column primary
  keys (`_number`/`_no`), snake_case prefix groups, and the `related_*`
  convention.

In both cases the platform produced too-few entities/relationships until
new rules were added. The underlying message from the user: *the platform
itself should figure this out — across any data source, every time.*
That is the spirit of this enhancement.
