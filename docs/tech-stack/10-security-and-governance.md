# Security and Governance

## 1. Security Posture Summary

Weave operates as an internal enterprise platform with API-first access control. The current release emphasizes inbound API key authentication, fabric-level guardrails, and ontology audit trails. Full SSO, RBAC, and enterprise IAM integration are roadmap items (Phase 5).

This document describes implemented controls and planned hardening.

---

## 2. Authentication

### 2.1 Inbound API key middleware

Module: `backend/app/core/security.py` — `InboundAPIKeyMiddleware`

| Caller type | X-API-Key requirement |
|-------------|----------------------|
| Localhost / private LAN (RFC1918) | Optional |
| Tunnelled traffic (ngrok, forwarded headers) | Required |
| Public internet | Required |

Protected scope: all `/api/v1/*` routes except documented public endpoints.

### 2.2 Public endpoints (no key)

| Path | Purpose |
|------|---------|
| / | API root |
| /health | Health check |
| /docs, /redoc | OpenAPI documentation |
| /openapi.json, /api/v1/openapi.json | Schema |
| /uploads/* | Static uploaded files |

### 2.3 API key lifecycle

| Operation | Tool |
|-----------|------|
| Issue key | scripts/issue_api_key.py |
| Storage | Hashed records in inbound_api_key_service |
| Validation | Header X-API-Key on each request |

Keys should be rotated on compromise and revoked via key service administration.

### 2.4 Escape hatches (non-production)

| Variable | Effect |
|----------|--------|
| INBOUND_AUTH_DISABLED=true | Disables middleware globally |
| INBOUND_AUTH_BYPASS_PATHS | Comma-separated additional exempt prefixes |

These must not be enabled on internet-facing deployments.

---

## 3. LLM Key Handling (BYOK)

For external API consumers invoking `/query`:

| Header | Purpose |
|--------|---------|
| X-LLM-API-Key | Caller-supplied OpenAI/Anthropic/Gemini key |

Local development callers may rely on server-configured provider keys in environment variables. Server keys must be stored in a secrets manager in production, never committed to source control.

`/retrieve` does not call external LLMs and does not require BYOK.

---

## 4. CORS Policy

Configured in `main.py`:

- Allowed origins: localhost:3000, 127.0.0.1:3000, plus KF_CORS_ORIGINS
- Regex allowance for ngrok subdomains (development tunnels)
- Credentials enabled for cookie-based future auth

Production deployments should restrict origins to known frontend hostnames.

---

## 5. Fabric Guardrails

Per-fabric governance profiles stored in `fabrics.guardrails` (JSON).

| Field | Purpose |
|-------|---------|
| allowed_topics | Restrict query subject matter |
| blocked_terms | Term deny list |
| max_response_length | Output length cap |
| require_citations | Enforce source attribution in responses |
| pii_handling | Policy flag for PII treatment |

Endpoints:

- GET fabric details include guardrails
- PUT /api/v1/knowledge/{fabric_id}/guardrails

Guardrails are applied during query synthesis in the knowledge endpoint layer.

---

## 6. Ontology Governance

### 6.1 Version immutability

Approved ontology versions cannot be modified. Changes require a new version and re-approval.

### 6.2 Element review

| Action | Endpoint |
|--------|----------|
| Approve elements | POST /api/v1/ontology/review/approve |
| Reject elements | POST /api/v1/ontology/review/reject |
| Approve version | POST /api/v1/graph/ontology/versions/{id}/approve |

### 6.3 Audit trail

| Storage | Content |
|---------|---------|
| ontology_audit_logs table | DB-backed audit events |
| ontology_data enrichment JSON | Legacy file audit (dual-write path) |

Events include actor, action, target element, timestamp, and metadata payload.

### 6.4 Evidence requirements

Production policy (recommended): relationships should carry OntologyEvidence linking to source tables, columns, or document spans before version approval.

---

## 7. Data Classification and Handling

| Data class | Location | Sensitivity |
|------------|----------|-------------|
| Source warehouse rows | Chroma chunks, connection_info samples | High — customer data |
| Uploaded PDFs | KF_UPLOAD_DIR | High |
| Ontology definitions | PostgreSQL ontology tables | Medium — semantic metadata |
| Canonical graph | graph_nodes, graph_edges | Medium |
| API keys (inbound) | Hashed key store | Critical |
| LLM provider keys | Environment / BYOK header | Critical |

Operators should classify fabrics by data sensitivity and restrict network access accordingly.

---

## 8. Network Security

| Control | Recommendation |
|---------|----------------|
| TLS termination | Reverse proxy (nginx, ALB, ingress) in production |
| Database | Private subnet; no public Postgres port |
| Neo4j / Stardog | VPC peering or private endpoints only |
| Tunnel exposure | Require API keys; disable INBOUND_AUTH_DISABLED |

---

## 9. Secrets Management

| Secret | Storage pattern |
|--------|-----------------|
| DATABASE_URL | Secrets manager / K8s secret |
| OPENAI_API_KEY | Secrets manager |
| NEO4J_PASSWORD | Secrets manager |
| STARDOG_PASSWORD | Secrets manager |
| SECRET_KEY | Rotate from default; secrets manager |
| Databricks / Snowflake tokens | Per-fabric connection_info (encrypted at rest — roadmap) |

Current release stores connection credentials in fabric connection_info JSON. Enterprise hardening should add field-level encryption or external vault references.

---

## 10. Input Validation

| Layer | Mechanism |
|-------|-----------|
| API | Pydantic v2 request models |
| File upload | Extension allow list, MAX_FILE_SIZE (100 MB) |
| SQL connectors | Parameterized queries where applicable |
| Job config | JSON schema validation in job service |

---

## 11. Authorization Model

| Capability | Current state |
|------------|---------------|
| Authenticated vs anonymous | API key presence for external callers |
| Role-based access (admin, analyst, viewer) | Planned |
| Fabric-level ACL | Planned |
| SSO (OIDC/SAML) | Planned |

All authenticated callers currently share equivalent API access. Deploy behind network controls until RBAC is implemented.

---

## 12. Compliance Considerations

| Topic | Weave support |
|-------|---------------|
| Audit logging | Ontology audit logs; platform job history |
| Data residency | Self-hosted deployment model supports customer-controlled regions |
| Right to erasure | DELETE /api/v1/knowledge/{fabric_id} removes fabric and associated index entries |
| Model training on customer data | Optional ML training uses fabric-local data; no default external training |

Formal SOC 2 / HIPAA certification is an organizational process outside the application codebase.

---

## 13. Vulnerability Management

| Practice | Guidance |
|----------|----------|
| Dependency updates | Monitor requirements.txt and package.json |
| Container scanning | Scan backend and frontend images in CI |
| API exposure | Disable /docs on public internet or protect with auth |

---

## 14. Incident Response

Recommended procedures:

1. Revoke compromised inbound API keys via issue_api_key administration
2. Rotate LLM and database credentials
3. Review ontology_audit_logs and platform_jobs for anomalous activity
4. Restore from Postgres and Chroma backup if data integrity is affected

---

## 15. Security Roadmap

| Item | Phase |
|------|-------|
| SSO / OIDC integration | Phase 5 |
| RBAC with fabric scopes | Phase 5 |
| Encrypted connection_info vault | Phase 5 |
| Structured security event logging | Phase 5 |
| Rate limiting at application layer | Phase 5 |

Refer to docs/PRODUCTION_PLATFORM_ROADMAP.md for full phase plan.

---

## 16. Document Suite Complete

Return to [README.md](./README.md) for the full documentation index.
