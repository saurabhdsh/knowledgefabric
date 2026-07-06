# Enhancement: HTTPS / External Access for Knowledge Fabric

> **Status:** Proposed — not implemented
> **Owner:** TBD
> **Priority:** High — blocks any third-party agent consumption
> **Last updated:** 2026-05-25

---

## 1. Problem Statement

The Knowledge Fabric API today is reachable only on `http://localhost:8000`
and CORS is hardcoded to `http://localhost:3000`. To let any external
agent (CSNP CLI from another machine, partner agents, hosted LangChain /
LangGraph nodes, etc.) consume the fabric we need an **HTTPS endpoint**.

User intent (paraphrased): *"Can we keep the frontend running locally and
just expose the backend over HTTPS?"* Yes — and that's the simplest path
to ship. This document records the recommended approach so we can revisit
it as a planned piece of work.

---

## 2. Target Architecture

Frontend stays local, backend stays local, a **tunnel** in front of the
backend provides a public HTTPS URL.

```
Your Mac                                       The Internet
─────────                                      ─────────────
  frontend  ──HTTP──►  backend                                       │
  (localhost:3000)    (localhost:8000)         external agents       │
                            ▲                       │                │
                            │                       │ HTTPS          │
                            └────────── tunnel ─────┘                │
```

- **Frontend** keeps running on `http://localhost:3000` (no change to
  dev workflow). It calls the backend at `http://localhost:8000` exactly
  as today.
- **Backend** keeps running on `http://localhost:8000`.
- A tunnelling agent on the same machine maps a public HTTPS URL to the
  local port. External agents call the HTTPS URL. The frontend never
  sees the tunnel and never has to change.

Key property: the local development experience is **untouched**.

---

## 3. Why Vercel (and other JAMstack platforms) Are NOT the Backend Host

For completeness, this enhancement explicitly rejects Vercel /
Netlify / Cloudflare Workers / Deno Deploy as a backend host because the
backend violates every assumption they make:

| Platform assumption | Reality of our backend |
|---|---|
| Functions complete in seconds | LLM + vector retrieval routinely exceeds 60 s |
| Stateless / no disk | ChromaDB persistent dir, `fabrics.json`, `uploads/` |
| Tiny dependencies (~50–250 MB) | `torch`, `transformers`, `sentence-transformers`, `xgboost`, `chromadb`, `pyarrow` (~2–3 GB) |
| No background workers | `training_service.threading.Thread`; multi-stage discovery orchestrator |
| One process per request | FastAPI is a long-running ASGI app with caches & pools |

Those platforms ARE great for the **frontend**. Don't put the backend
there.

---

## 4. Recommended Tunnel Options

| Tool | Command | Best for | Notes |
|---|---|---|---|
| **ngrok** | `ngrok http 8000` | Quick demo — public HTTPS URL in 60 seconds | Free tier gives random URL; paid gives stable subdomain. Built-in basic auth, OAuth, IP allowlist. |
| **Cloudflare Tunnel** (`cloudflared`) | `cloudflared tunnel run <name>` | Permanent staging on **your own domain** (e.g. `api.weave-dev.yourdomain.com`) | Free forever. Survives reboots. Pairs with Cloudflare Access for SSO/MFA gating. |
| **Tailscale Funnel** | `tailscale funnel 8000` | Sharing with a small named team via Tailscale identity | Strongest identity model; consumers may need to be on Tailnet for some modes. |

**Default recommendation for the first external-agent demo: ngrok.**
**Default recommendation for an always-on staging URL: Cloudflare Tunnel
on your own domain.**

---

## 5. Security Layers That MUST Be Wired Before Going Public

A tunnel gives you HTTPS and nothing else. The moment that URL is
internet-reachable, the following are non-negotiable:

### 5.1 Inbound authentication
- Extend the existing `api_key_service` to issue **inbound** keys
  per consumer (separate from outbound LLM-provider keys it manages
  today).
- Middleware on every protected route validates `X-API-Key` against the
  hashed key store.
- The frontend on localhost can be exempted via a Host header check
  (`Host: localhost:8000`) OR can use a dedicated dev key.

### 5.2 Per-fabric authorization
- Use the existing `guardrails` block on each fabric
  (`data_classification`, `pii_fields`, `approved_roles`,
  `enforce_masking`) as the canonical ACL.
- Middleware loads the fabric for the target `fabric_id`, evaluates
  whether the resolved consumer identity satisfies the guardrails, and
  optionally masks `pii_fields` on the response.

### 5.3 Rate limiting & cost caps
- `slowapi` (or equivalent) middleware for per-key request rate (e.g.
  60 req/min default).
- Per-key daily LLM-token quota so a runaway agent cannot drain OpenAI
  spend.
- Concurrency cap per key to protect ChromaDB and the model layer.

### 5.4 CORS
- Keep `localhost:3000` allowlisted for the local frontend.
- Add per-consumer browser-origin allowlists if a hosted UI ever
  consumes the fabric.
- External agents are server-side; they do not require CORS.

### 5.5 Audit log
- Every authentication outcome, authorization decision, and tunnelled
  request lands in the existing `AuditTrail` table.
- Useful for HIPAA / SOC 2 audits and for debugging consumer issues.

### 5.6 Edge belt-and-braces (optional but cheap)
- Both ngrok and Cloudflare Tunnel can layer an additional auth in
  front of the tunnel (basic auth / OAuth / mTLS / Cloudflare Access).
- Enable this in addition to the X-API-Key middleware.

---

## 6. CORS & Frontend Behaviour

Frontend behaviour does not change.

| Request origin | Target | Auth needed | CORS allowed |
|---|---|---|---|
| Frontend on `localhost:3000` | Backend on `localhost:8000` (direct) | None (or dev key) | Yes — existing config |
| External agent (anywhere) | Backend via tunnel HTTPS URL | `X-API-Key` required | N/A — server-side caller |

The frontend never hits the tunnel URL in the recommended setup.

---

## 7. Known Limitations of the Tunnel Approach

These are reasons teams eventually graduate off tunnels — not blockers
for v1:

1. **Mac sleep / shutdown kills it.** Tunnel and backend both stop when
   the laptop sleeps. Fine for demos, blocks 24 / 7 usage.
2. **All external load runs on your laptop.** `torch` + ChromaDB +
   OpenAI calls share CPU/memory with the rest of your workflow.
3. **No high availability.** A single point of failure by definition.
4. **Tunnel URL may change** (free ngrok subdomain rotates per session).
5. **Bandwidth cap on free tiers.**

---

## 8. Graduation Path

When any of the above hits a real limit, move the backend to a managed
host **without changing the frontend**:

### 8.1 Frontend can either stay local OR move to Vercel
Vercel is an excellent fit for the React frontend (auto HTTPS, global
CDN, preview deploys per PR, free tier for staging). It's optional —
local frontend continues to work.

### 8.2 Backend goes to a PaaS that supports long-running stateful services
Recommended order of preference for our specific workload:

| Platform | Why it fits | Notes |
|---|---|---|
| **Render** ⭐ | Web service + persistent disk + cron + workers; auto HTTPS; GitHub-driven | Closest UX to "Vercel for backends" |
| **Railway** ⭐ | GitHub-driven deploys, attach Postgres/Redis as siblings | Usage-based pricing can spike |
| **Fly.io** | Docker + persistent volumes + multi-region | Need `Dockerfile` + `fly.toml`; more control |
| **DigitalOcean App Platform** | Container + managed Postgres + S3-compatible Spaces | Reliable, cheap |
| **GCP Cloud Run** | Serverless containers; up to 60-min request timeout | Cold starts; persistent disk needs Cloud Filestore |
| **AWS App Runner / ECS Fargate** | Maximum control, enterprise trust | Steeper operational curve |

### 8.3 Data layer adjustments at graduation time

| Today (local) | After graduation |
|---|---|
| `/app/data/fabrics.json` | Persistent disk on Render/Railway *or* move to managed Postgres for multi-instance support |
| `/app/uploads/...` | S3 / Cloudflare R2 / DigitalOcean Spaces via signed URLs |
| ChromaDB persistent dir | Persistent volume on the same instance, OR managed vector DB (Pinecone / Qdrant Cloud / Chroma Cloud / Weaviate) when horizontal scaling is needed |

### 8.4 Edge / WAF layer (production)
Put **Cloudflare** (free tier) in front of whichever PaaS you choose for
WAF, DDoS protection, edge rate-limiting, and a single point to manage
CORS and per-consumer origin allowlists.

---

## 9. Phased Rollout

### Phase 0 — Today
- Frontend on `localhost:3000`, backend on `localhost:8000`. No external
  access.

### Phase 1 — First external agent (this week)
- `brew install ngrok` (or install `cloudflared`).
- `ngrok http 8000` → copy the HTTPS URL.
- Add `X-API-Key` middleware to FastAPI; issue per-consumer keys via
  the existing `api_key_service` (extended for inbound use).
- Per-fabric authorization driven by the existing `guardrails` block.
- Basic `slowapi` rate limit (60 req/min default).
- Hand the HTTPS URL + key to each external agent (CSNP CLI included).

### Phase 2 — Always-on staging (next sprint)
- Acquire a domain or subdomain (e.g. `api.weave-dev.yourdomain.com`).
- Switch to **Cloudflare Tunnel** so the URL is stable and survives
  reboots.
- Add **Cloudflare Access** for an additional OAuth/MFA layer at the
  edge.
- Add per-key LLM-token quotas and audit trail wiring.

### Phase 3 — Production (this quarter)
- Move backend to **Render** (or equivalent PaaS).
- Move uploads to **Cloudflare R2** / S3 with signed URLs.
- Frontend can move to **Vercel** (optional) or stay local.
- **Cloudflare** in front of everything as the edge / WAF.
- OpenTelemetry tracing end-to-end.
- Tenant model + per-tenant isolation in storage + DB.

### Phase 4 — Enterprise / regulated customers (later)
- PrivateLink / VPC peering with named enterprise customers.
- Bring-your-own-CA for mTLS.
- BYO encryption keys at rest.
- Region-pinned deployments for data residency.

---

## 10. Practical "Day-1" Checklist

When implementing Phase 1, the work concentrates in three places:

1. **Edge layer (outside the app code)**
   - [ ] Install and run `ngrok http 8000` (or `cloudflared`).
   - [ ] Record the HTTPS URL and treat it as a secret in agent
         configuration.

2. **FastAPI middleware**
   - [ ] `X-API-Key` validator → resolves `consumer_id` from a hashed
         key store.
   - [ ] Per-fabric authz check against `guardrails.approved_roles`
         and `guardrails.data_classification`.
   - [ ] Rate limit (`slowapi`) per key.
   - [ ] PII masking on response when `guardrails.enforce_masking`.

3. **Operations**
   - [ ] Audit log writes for every authn/authz outcome.
   - [ ] Per-key usage endpoint (`GET /api/v1/usage/me`) so consumers
         can self-serve their quotas.
   - [ ] Documented onboarding flow for issuing a new consumer key.

---

## 11. Affected Code (At Implementation Time)

| Path | Change |
|---|---|
| `backend/app/main.py` | Add auth middleware; make CORS allowlist dynamic per consumer |
| `backend/app/services/api_key_service.py` | Extend with inbound-key issuance, hashing, lookup, rotation, revocation |
| `backend/app/core/security.py` | **NEW** — middleware: X-API-Key resolver, per-fabric authz |
| `backend/app/core/ratelimit.py` | **NEW** — `slowapi` config |
| `backend/app/api/v1/endpoints/usage.py` | **NEW** — `/api/v1/usage/me` for consumers to read their quota |
| `backend/app/services/audit_service.py` | Route authn/authz decisions into existing `AuditTrail` |
| `frontend/src/utils/api.ts` | Optional: dev mode header so frontend continues to work without an inbound key |

---

## 12. Open Questions

1. **Dev key vs Host exemption** for the frontend — issue every developer
   a dev-scoped key, or exempt requests with `Host: localhost:*`?
   Recommendation: dev key, scoped to the developer, expires in 30 days.
2. **Token format** — opaque random string + bcrypt hash, or JWT with
   embedded scopes? Recommendation: opaque + hash for v1, JWT later if
   we add OAuth / OIDC.
3. **Pricing posture for external consumers** — free tier with low
   quotas vs invite-only? Out of scope for this doc but needed before
   onboarding.

---

## 13. Out of Scope (For Now)

- Self-service consumer signup UI (issue keys manually for v1).
- Multi-tenant data isolation (covered in §8 graduation step).
- Cross-region deployments / data residency.
- Real-time / WebSocket streams to external consumers.

---

## Appendix A — Why this came up

This document was created after the conversation about exposing the
fabric to external agents and confirming that the frontend can remain on
`localhost:3000`. The recurring user intent was:

> *"Lets have frontend running on local."*

So the recommended pattern is: **don't touch the frontend, put a tunnel
in front of the backend, layer auth + rate-limit + audit on top.** This
is the minimum-effort path to a real HTTPS endpoint without disturbing
local development. When that pattern hits its limits, the graduation
path in §8 moves the backend onto a PaaS while the frontend keeps
running locally (or optionally moves to Vercel).
