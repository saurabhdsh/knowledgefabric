# Source Integrations

## 1. Integration Philosophy

Weave normalizes heterogeneous enterprise sources into Knowledge Fabrics. A fabric is the unit of:

- Vector indexing (semantic recall)
- Ontology discovery input (schema or document artifacts)
- Canonical graph scope
- Retrieval and query API addressing

Connectors are responsible for authentication, query execution, row retrieval, and metadata capture. The platform layer handles chunking, embedding, and persistence.

---

## 2. Supported Source Types

| Source | Connector mechanism | Fabric source_type | Ontology input |
|--------|---------------------|-------------------|----------------|
| Databricks | Statement Execution REST API | database | Schema profile + sample rows |
| Snowflake | snowflake-connector-python | database | Schema profile + sample rows |
| PostgreSQL | psycopg2 | database | Schema profile |
| MySQL | mysql.connector | database | Schema profile |
| SQLite | sqlite3 | database | Schema profile |
| MongoDB | pymongo | database | Collection schema + documents |
| CSV upload | pandas in-process | database | Column inference |
| PDF | PyPDF2 via document_service | pdf | Fabric artifact bridge |
| TXT | Direct read | pdf | Fabric artifact bridge |
| DOCX | python-docx (ontology path) | ontology artifact | Document pipeline |
| XML | Custom processor | ontology artifact | Document pipeline |
| ServiceNow | Structured incident export | servicenow | Structured graph path |
| Composite | Multi-fabric merge | composite | Inherited from sources |

---

## 3. Databricks Integration

### 3.1 Connection parameters

| Field | Description |
|-------|-------------|
| server_hostname | Workspace URL |
| warehouse_id | SQL warehouse identifier |
| access_token | Personal access token or OAuth token |
| catalog | Unity Catalog name |
| schema | Schema name |
| table | Table name (optional for custom SQL) |

### 3.2 Execution model

Queries execute via Databricks Statement Execution REST API with asynchronous polling until completion. Results are normalized to row dictionaries and passed to `document_service.process_database_data`.

### 3.3 Metadata captured in connection_info

- type: databricks
- catalog, schema, table
- columns and sample_rows (for ontology schema analyzer)
- rows_imported count

---

## 4. Snowflake Integration

### 4.1 Connection parameters

| Field | Description |
|-------|-------------|
| account | Snowflake account identifier |
| user, password | Credentials |
| warehouse | Compute warehouse |
| database, schema | Target namespace |
| table | Optional table name |

### 4.2 Driver

`snowflake-connector-python` establishes JDBC-equivalent connection. Query results stream into the same chunk pipeline as Databricks.

---

## 5. Relational Database Integration

PostgreSQL, MySQL, and SQLite connectors accept standard host, port, database, user, password, and query or table parameters. Connection validation occurs before fabric creation via test endpoints.

Row metadata embedded in chunks includes table and column names to support downstream structured query detection.

---

## 6. MongoDB Integration

MongoDB connector supports connection string, database, collection, and optional query filter. Documents serialize to text representations for chunking. Used heavily in ITSM and operational document stores.

---

## 7. CSV Integration

### 7.1 Modes

| Mode | Endpoint pattern | Behavior |
|------|------------------|----------|
| Live profile | create-database-fabric-csv | Upload CSV with database profile tag |
| Preview | preview-database-csv | Schema inference without fabric creation |

CSV rows receive the same chunk schema as warehouse rows. Database profile tags (mongodb, databricks, snowflake, etc.) influence ontology rule packs.

---

## 8. Document Integration

### 8.1 Knowledge Fabric uploads (PDF/TXT)

Files land in `backend/uploads/`. `create-pdf-fabric`:

1. Extracts text (PyPDF2 or direct read)
2. Chunks via `document_service.chunk_text`
3. Indexes in Chroma under fabric_id
4. Records `processed_files` in fabric metadata
5. Enqueues ontology discovery job

### 8.2 Ontology Studio uploads (PDF/DOCX/XML/Images)

Files land in `ontology_data/uploads/`. Processed by dedicated processors:

| Processor | Module |
|-----------|--------|
| PDF | pdf_processor |
| DOCX | docx_processor |
| XML | xml_processor |
| Images (OCR) | image_processor + pytesseract |

### 8.3 Fabric-to-ontology bridge

When discovery runs for a PDF fabric without ontology uploads, `fabric_artifact_bridge`:

1. Resolves PDF paths from `uploads/` via `processed_files`
2. Falls back to materializing vector chunks as XML in ontology uploads

---

## 9. ServiceNow Integration

Structured ServiceNow incident fabrics use `_build_structured_servicenow_graph` for exploratory visualization and can feed ontology materialization when structured fields are present.

---

## 10. Composite Fabrics

Composite fabrics merge multiple source fabrics into a unified vector index with `composite_origin_source_name` metadata. Guardrails merge conservatively (highest data classification wins).

---

## 11. Chunk Schema (Unified)

All tabular sources produce chunks with consistent metadata:

```json
{
  "content": "row or field text",
  "metadata": {
    "source_id": "fabric_id",
    "source_name": "table_or_file",
    "table": "optional",
    "row": "optional",
    "columns": "optional"
  }
}
```

This schema enables cross-source ontology discovery and structured query heuristics.

---

## 12. Connector Validation

Pre-flight validation endpoints return actionable errors before job enqueue:

- Databricks: token, warehouse, permissions
- Snowflake: account connectivity
- Relational: TCP and authentication
- CSV: encoding, delimiter, empty file detection

---

## 13. Future Connector Roadmap

| Source | Priority | Notes |
|--------|----------|-------|
| Amazon Redshift | Medium | JDBC pattern similar to Snowflake |
| Azure Synapse | Medium | ODBC/JDBC |
| S3 / ADLS parquet | Medium | Batch ingest job |
| Kafka / event streams | Low | Delta ontology refresh |
| SAP / ERP exports | Low | Domain packs |

---

## 14. Next Document

See [05-ontology-and-graph.md](./05-ontology-and-graph.md) for ontology pipeline and graph storage architecture.
