# Partner Access Guide — Exposing the Knowledge Fabric over HTTPS

This is the **operator runbook** for letting an external Python agent (a partner,
a customer's bot, your own laptop's CSNP CLI, etc.) hit the Knowledge Fabric API
over HTTPS — with per-consumer API keys **and Bring-Your-Own-LLM-Key (BYOK)** —
using **ngrok** as a tunnel from your laptop or any host.

> **Two keys per partner** — keep them straight:
>
> | Header | What it is | Who issues it | What it protects |
> |---|---|---|---|
> | `X-API-Key`     | `kf_live_…` | **You (the operator)** via `scripts/issue_api_key.py` | Inbound auth to your fabric |
> | `X-LLM-API-Key` | `sk-…`      | **The partner's own OpenAI account** | Pays for LLM calls (partner is billed, never you) |
>
> External partners MUST send both. Local browser/dev traffic auto-exempts on
> both and uses the server's `OPENAI_API_KEY`.

It pairs with two other docs:

- [`ENHANCEMENT_HTTPS_EXTERNAL_ACCESS.md`](./ENHANCEMENT_HTTPS_EXTERNAL_ACCESS.md) — the architectural rationale for the design.
- [`../API_DOCUMENTATION.md`](../API_DOCUMENTATION.md) — the full API surface partners can call.

---

## Table of contents

1. [Topology — what gets connected to what](#1-topology--what-gets-connected-to-what)
2. [One-time host setup](#2-one-time-host-setup)
3. [Per-session: start the tunnel](#3-per-session-start-the-tunnel)
4. [Issue an API key for a new partner](#4-issue-an-api-key-for-a-new-partner)
5. [What you hand the partner](#5-what-you-hand-the-partner)
6. [The partner's Python client](#6-the-partners-python-client)
7. [Security model in one page](#7-security-model-in-one-page)
8. [Managing keys (list, revoke, scope, expire)](#8-managing-keys-list-revoke-scope-expire)
9. [Troubleshooting](#9-troubleshooting)
10. [Going to production (replacing ngrok)](#10-going-to-production-replacing-ngrok)

---

## 1. Topology — what gets connected to what

```text
            Partner laptop / their server
                       │
                       │  HTTPS + X-API-Key header
                       ▼
        https://abcd-1234.ngrok-free.app
                       │  (ngrok tunnel running on YOUR machine)
                       ▼
                  localhost:8000   on your Mac
                       │
                       ▼
               ┌──────────────┐
               │ Knowledge    │  ← uvicorn (native)  OR  docker compose backend
               │ Fabric API   │     both share the same backend/data/ on disk
               └──────────────┘
```

Key properties of this setup:

- The partner only ever sees the `https://….ngrok-free.app` URL.
- They never know (or care) whether your backend is running via Docker or via
  `uvicorn`. You can switch any time — same URL, same key.
- The Knowledge Fabric API enforces an **inbound API key** (`X-API-Key` header)
  on all `/api/v1/*` routes when the request comes from outside your laptop's
  local network. Local browser traffic from `http://localhost:3000`
  (your React frontend) is auto-exempt so dev flow keeps working.
- Keys are stored hashed in `backend/data/inbound_api_keys.json`. Plain keys are
  shown exactly once at issuance.

---

## 2. One-time host setup

### 2.1 Install ngrok

```bash
brew install ngrok
ngrok config add-authtoken <YOUR_NGROK_AUTHTOKEN>    # free signup at ngrok.com
```

### 2.2 Confirm the backend has the auth middleware

Already installed in this repo:

- `backend/app/core/security.py` — `InboundAPIKeyMiddleware`
- `backend/app/services/inbound_api_key_service.py` — JSON-backed key store
- `backend/app/main.py` — middleware is registered and CORS allows
  `*.ngrok.io` / `*.ngrok-free.app` / `*.ngrok.app`

Behavior summary:

| Caller | Headers | Outcome |
|---|---|---|
| Browser at `http://localhost:3000` → backend on `localhost:8000` | none | 200 (local exempt) |
| Docker frontend container → backend container (private IP) | none | 200 (private-LAN exempt) |
| Anything via ngrok (carries `X-Forwarded-For` / `ngrok-*`) | none | **401** — key required |
| Same, with valid `X-API-Key` | `X-API-Key: kf_live_…` | 200 |
| Same, with invalid/expired/revoked key | `X-API-Key: bad` | 401 |

Escape hatches (env vars on the backend):

| Variable | Effect |
|---|---|
| `INBOUND_AUTH_DISABLED=true` | Globally disable the key check (NOT recommended on public hosts) |
| `INBOUND_AUTH_BYPASS_PATHS=/api/v1/foo,/api/v1/bar` | Extra exempt path prefixes |
| `KF_CORS_ORIGINS=https://myapp.example.com` | Additional allowed CORS origins |

### 2.3 Start the backend

Pick **one** of these. Don't run both at the same time on port 8000.

```bash
# Option A — native uvicorn
cd /Users/saurabhdubey/KF/Knowledge-Fabric/backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
# Option B — Docker compose
cd /Users/saurabhdubey/KF/Knowledge-Fabric
docker compose up -d backend
docker compose logs -f backend
```

Both runtimes read/write the **same files** in `backend/data/`, `backend/uploads/`,
`backend/chroma_db/`, `backend/models/`, `backend/ontology_data/` via bind mounts.
Anything created in one runtime is visible in the other instantly. No migration
needed.

Verify with:

```bash
curl -s http://localhost:8000/health
# -> {"status":"healthy","service":"knowledge-fabric-api"}
```

---

## 3. Per-session: start the tunnel

```bash
ngrok http 8000
```

It prints something like:

```text
Session Status     online
Forwarding         https://abcd-1234.ngrok-free.app -> http://localhost:8000
```

Copy the `https://…ngrok-free.app` URL. Test it from anywhere:

```bash
curl -s https://abcd-1234.ngrok-free.app/health
# -> {"status":"healthy","service":"knowledge-fabric-api"}
```

> **Heads-up — free-tier ngrok URLs rotate.** Every time you start `ngrok http
> 8000` you get a new subdomain. Either reserve a static domain in your ngrok
> dashboard (paid feature) or accept that you re-share the URL when you restart
> the tunnel. For long-lived integrations consider Cloudflare Tunnel, AWS App
> Runner, or any of the production options in section 10.

---

## 4. Issue an API key for a new partner

Each partner gets their own key. Keys can be scoped to specific fabrics and / or
given an expiry date.

```bash
# Most common — one key per partner, all fabrics, no expiry
python scripts/issue_api_key.py issue \
    --name "acme-corp-agent" \
    --description "ACME Corp diabetic-care agent"
```

Restrict to specific fabrics:

```bash
python scripts/issue_api_key.py issue \
    --name "acme-corp-agent" \
    --fabric-ids fabric_workspace_default_csnp_members_tables_1779712046,fabric_snowflake_csv_claims_duplicate_agentic_2000_2000rows_1778241582
```

Add a rotation date:

```bash
python scripts/issue_api_key.py issue \
    --name "acme-corp-agent" \
    --expires-at 2026-08-26
```

What you see at issuance:

```text
╭──── API key issued ────╮
│ Key ID:       366c54a4b4dcd765
│ Name:         acme-corp-agent
│ Description:  ACME Corp diabetic-care agent
│ Scopes:       query
│ Fabric scope: all fabrics
│ Created:      2026-05-26T03:51:25Z
╰────────────────────────╯

┏━━ Plain key — copy now, this is the only time it will be shown ━━┓
┃ kf_live_HnmYRzgC6HVNoOOUY_MR01Z1Jfp2qTU1gW6Nuy0wsTg               ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

The plain key is **never recoverable** — only its SHA-256 hash is stored at
`backend/data/inbound_api_keys.json`. Copy the `kf_live_…` value now into the
secret manager / Slack DM / email you're sending the partner.

---

## 5. What you hand the partner

Three things from you, **plus** they bring their own OpenAI key.

| # | Value | Source | Example |
|---|---|---|---|
| 1 | HTTPS base URL | Your `ngrok http 8000` output | `https://abcd-1234.ngrok-free.app` |
| 2 | Inbound API key | Issued by you via `scripts/issue_api_key.py` | `kf_live_HnmYRzgC6HVNoOOUY_MR01Z1Jfp2qTU1gW6Nuy0wsTg` |
| 3 | Fabric ID(s) | UI sidebar or `GET /api/v1/knowledge/fabrics` | `fabric_workspace_default_csnp_members_tables_1779712046` |
| 4 | **LLM key (BYOK)** | **The partner's own OpenAI account — you NEVER provide this** | `sk-….` |
| 5 | Sample Python client | `scripts/csnp_agent_inline.py` | (file in repo) |

Copy-paste handoff template:

```text
Hi <name>, here are the credentials for your Knowledge Fabric integration:

  Base URL    :  https://abcd-1234.ngrok-free.app
  API key     :  kf_live_HnmYRzgC6HVNoOOUY_MR01Z1Jfp2qTU1gW6Nuy0wsTg
  Fabric ID   :  fabric_workspace_default_csnp_members_tables_1779712046

You also need:
  Your OpenAI sk-... key (BYOK). This stays on YOUR side — it pays for
  the LLM calls our backend makes on your behalf. Get one at
  https://platform.openai.com/api-keys

Every request must send:
  X-API-Key:      <kf_live_... key above>     ← authenticates you
  X-LLM-API-Key:  <your sk-... key>           ← only on /query/... — pays the LLM

The 90% endpoints are:
  GET  /api/v1/knowledge/{fabric_id}             — fabric metadata (no LLM key needed)
  POST /api/v1/knowledge/query/{fabric_id}       — { "query": "...", "top_k": 5 }   (LLM key required)

Attached: scripts/csnp_agent_inline.py — a ready-to-run reference client.
Edit the four constants at the top, then run:

  pip install requests rich
  python csnp_agent_inline.py
```

---

## 6. The partner's Python client

Two flavours ship with the repo:

### 6a. `scripts/csnp_agent_inline.py` — inline credentials + pluggable LLM (recommended for partners)

A self-contained file with **two phases**:

1. **Retrieve** chunks from your fabric (no LLM, no BYOK header — `POST /retrieve/{fabric_id}`).
2. **Synthesise** using **the partner's own LLM, locally**, via a pluggable `call_llm()` function.

Out of the box it supports OpenAI, Anthropic Claude, and Google Gemini. Adding a fourth provider (Llama on Ollama, Bedrock, a fine-tuned model, anything) is a 5-line function — edit `_call_custom()` and set `LLM_PROVIDER = "custom"`.

Constants to edit:

```python
# Fabric
KF_BASE_URL:    str = "https://abcd-1234.ngrok-free.app"
KF_API_KEY:     str = "kf_live_..."
KF_FABRIC_ID:   str = "fabric_workspace_default_csnp_members_tables_1779712046"

# Pluggable LLM (LOCAL to the partner's machine — never crosses the wire)
LLM_PROVIDER:   str = "openai"        # "openai" | "anthropic" | "gemini" | "custom"
LLM_API_KEY:    str = "sk-..."        # partner's own key for that provider
LLM_MODEL:      str = "gpt-4o-mini"   # whatever the provider accepts
```

Why this design is better than putting the LLM key in an HTTPS header:

- **The partner's LLM key never leaves their laptop.** No header, no logs, no network.
- **The operator's fabric is provider-agnostic.** Your backend only does retrieval. Anthropic, Gemini, local models — all work with zero backend changes.
- **You spend nothing.** No OpenAI bill for partner traffic; you can host an unlimited number of read-only partners.

Run:

```bash
pip install requests rich
python scripts/csnp_agent_inline.py
```

It will:

1. Validate the three constants (rejects placeholders).
2. Connect, show a "Connected" panel with fabric name / chunk count.
3. List 9 specialised C-SNP agents in a table.
4. Let the partner pick one (or `all`) and ask its default question — or supply
   a custom one.
5. Print the LLM answer (markdown-rendered) + cited chunks.

### 6b. `scripts/csnp_agents_cli.py` — env-var / flag version (for operators)

The same 9 agents and the same UX, but credentials come from env vars or CLI
flags so the operator doesn't hardcode anything:

```bash
export KF_BASE_URL=https://abcd-1234.ngrok-free.app
export KF_API_KEY=kf_live_…
export KF_LLM_API_KEY=sk-…             # YOUR OpenAI key (BYOK)
python scripts/csnp_agents_cli.py --fabric-id fabric_xxx
```

### 6c. The smallest possible client (any language, any LLM)

Two-step pattern — retrieve, then synthesise locally:

```python
import requests, os
from openai import OpenAI                  # or anthropic, google-generativeai, etc.

BASE_URL  = "https://abcd-1234.ngrok-free.app"
API_KEY   = "kf_live_..."                 # operator-issued
FABRIC_ID = "fabric_workspace_default_csnp_members_tables_1779712046"

# 1) Retrieve chunks — no LLM key needed, no BYOK header
chunks = requests.post(
    f"{BASE_URL}/api/v1/knowledge/retrieve/{FABRIC_ID}",
    headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
    json={"query": "Find diabetic members with the highest cost.", "top_k": 5},
    timeout=30,
).json()["data"]["chunks"]

context = "\n\n".join(f"#{c['rank']} {c['content']}" for c in chunks)

# 2) Synthesise with WHATEVER LLM you want — key stays on YOUR machine
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
answer = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are a C-SNP analyst. Use only the provided context."},
        {"role": "user", "content": f"Question:\nFind diabetic members with the highest cost.\n\nContext:\n{context}"},
    ],
).choices[0].message.content
print(answer)
```

Equivalent curl for the retrieval step alone:

```bash
curl -s -X POST "https://abcd-1234.ngrok-free.app/api/v1/knowledge/retrieve/<fabric_id>" \
  -H "X-API-Key: kf_live_..." \
  -H "Content-Type: application/json" \
  -d '{"query":"Find diabetic members with the highest cost.","top_k":5}'
```

### 6d. (Optional) Hosted-LLM mode — `POST /query/{fabric_id}` with `X-LLM-API-Key`

If a partner doesn't want to run an LLM SDK themselves, the legacy `/query/{fabric_id}` endpoint still works. It does retrieval + synthesis on the backend, demanding `X-LLM-API-Key` from the partner so they're billed for the OpenAI call. Use this when the partner just wants a one-shot answer with no integration work.

```bash
curl -s -X POST "https://abcd-1234.ngrok-free.app/api/v1/knowledge/query/<fabric_id>" \
  -H "X-API-Key: kf_live_..." \
  -H "X-LLM-API-Key: sk-..." \
  -H "Content-Type: application/json" \
  -d '{"query":"Find diabetic members with the highest cost.","top_k":5}'
```

In practice **prefer the retrieve-only flow** (6c) for new partners — it's simpler on the wire, model-agnostic, and the partner's LLM key stays on their machine.

---

## 7. Security model in one page

There are **two separate auth checks** for every external call. They run in
the order shown.

```
                 ┌──────────────────────────────────────────┐
                 │   FastAPI request lifecycle              │
                 │                                          │
   request ──▶  ├── CORS middleware                          │
                 │                                          │
                 │── (1) InboundAPIKeyMiddleware            ▼
                 │     • public paths (/, /health, /docs)   bypass
                 │     • CORS preflight (OPTIONS)           bypass
                 │     • _is_local_origin()?                bypass
                 │         loopback OR RFC1918 LAN
                 │         AND no X-Forwarded-* / ngrok-*
                 │     • X-API-Key valid + active?          continue
                 │     • else                               401
                 │                                          │
                 │── route handler  (e.g. /query/{fid})      │
                 │     │                                    │
                 │     └─ (2) _resolve_llm_key(request)      │
                 │             • X-LLM-API-Key set?          → use it (BYOK)
                 │             • else, local caller?         → server OPENAI_API_KEY
                 │             • else, external + missing    → 400 "BYOK required"
                 │             • else                         → 503
                 │                                          │
                 └── LLM call uses resolved key ──────────────┘
```

The two layers are deliberately decoupled:

- `X-API-Key` answers **"are you authorised to call this fabric?"**
- `X-LLM-API-Key` answers **"who pays for the OpenAI tokens this call burns?"**

A partner can have a valid `X-API-Key` but still get a 400 if they forget BYOK
— that's intentional, otherwise you'd silently fund their traffic.

What counts as "local" (no key needed):

- `request.client.host` is loopback (`127.0.0.1`, `::1`) **or** in one of:
  - `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` (RFC1918)
  - `169.254.0.0/16` (IPv4 link-local)
  - `fc00::/7`, `fe80::/10` (IPv6 ULA / link-local)
- AND the request does **not** carry any of:
  - `X-Forwarded-For`, `X-Forwarded-Host`, `X-Real-IP`, `Forwarded`
  - any `ngrok-*` header

ngrok always sets at least one of those forwarding headers, so tunnelled
traffic always falls through to the API-key check, **even though the TCP
client IP is `127.0.0.1` from the backend's perspective**.

What's stored in `backend/data/inbound_api_keys.json`:

```json
[
  {
    "id": "366c54a4b4dcd765",
    "name": "acme-corp-agent",
    "description": "ACME Corp diabetic-care agent",
    "display_prefix": "kf_live_HnmY",
    "key_hash": "<sha256 hex>",
    "scopes": ["query"],
    "fabric_ids": null,
    "created_at": "2026-05-26T03:51:25Z",
    "last_used_at": "2026-05-26T04:02:11Z",
    "expires_at": null,
    "revoked": false
  }
]
```

Plain keys are **never** stored — only the SHA-256 hash. Display prefix is for
human-readable listings.

---

## 8. Managing keys (list, revoke, scope, expire)

All commands run from the repo root with the backend venv active.

### List

```bash
python scripts/issue_api_key.py list
```

Shows each key's ID, name, scopes, fabric scope, created/last-used timestamps,
and status (active / expires-on / revoked).

### Revoke (immediate, no restart needed)

```bash
python scripts/issue_api_key.py revoke --id <key-id>
```

The next request using that key gets 401. The middleware re-reads the JSON file
on every request, so revocation is instant for any running backend (uvicorn or
Docker).

### Rotate

```bash
# 1) Issue a new key for the same partner
python scripts/issue_api_key.py issue --name "acme-corp-agent" --description "rotation 2026-Q3"

# 2) Send the new kf_live_… to the partner; they swap it in.

# 3) After the partner confirms, revoke the old one
python scripts/issue_api_key.py revoke --id <old-key-id>
```

### Scope tightly

If you want a partner key to only work for specific fabrics:

```bash
python scripts/issue_api_key.py issue \
    --name "acme-corp-agent" \
    --fabric-ids fabric_a,fabric_b
```

> Note: scope is currently recorded on the key (visible in `list`); fabric-level
> enforcement is enforced at the application layer — see
> `request.state.consumer_fabric_ids` if you want to add programmatic checks in
> the endpoint handlers.

---

## 9. Troubleshooting

### Partner gets `401 Missing X-API-Key header...`

They forgot the header. Sanity-check:

```bash
curl -i -X GET "https://abcd.ngrok-free.app/api/v1/knowledge/fabrics"
# should be 401

curl -i -X GET "https://abcd.ngrok-free.app/api/v1/knowledge/fabrics" \
  -H "X-API-Key: kf_live_..."
# should be 200
```

### Partner gets `401 Invalid, expired, or revoked API key.`

Confirm via `python scripts/issue_api_key.py list` that:

- the key ID is **active**, not revoked;
- `expires_at` is in the future or null;
- the `display_prefix` matches the first 12 chars of what the partner says they're using.

If everything looks right and it still fails, the key was probably copied with a
trailing whitespace or partial value. Issue a fresh one and re-send.

### Partner gets `400 This endpoint requires an LLM key...`

They sent a valid `X-API-Key` but forgot `X-LLM-API-Key`. This is by design —
partners pay for their own LLM calls. Tell them to set their OpenAI key:

```bash
export KF_LLM_API_KEY=sk-…
# or set KF_LLM_API_KEY constant in csnp_agent_inline.py
```

### Partner gets `404 Not Found` on `/{fabric_id}`

Either the fabric ID is wrong, or it was deleted, or the key is scoped to a
different fabric. Verify with:

```bash
curl -s "https://abcd.ngrok-free.app/api/v1/knowledge/fabrics" \
  -H "X-API-Key: kf_live_..." | python3 -m json.tool | head -40
```

### Frontend says "Load failed. Please check backend server and refresh."

This means the local React app can't reach the backend.

- Native uvicorn: confirm it's actually listening on `0.0.0.0:8000`.
- Docker: confirm the container is running (`docker compose ps`) and the bind
  mounts are correct (`docker inspect $(docker compose ps -q backend)
  --format '{{range .Mounts}}{{.Type}}  {{.Source}} -> {{.Destination}}{{println}}{{end}}'`).

If the backend is running and you still get 401s from the browser, the
middleware's local detection misread your network. Run a `docker compose down &&
docker compose up -d --force-recreate backend` to make sure the new compose
config (bind mounts + env vars) took effect.

### ngrok prints "Account requires a paid plan…" or rate-limits

You hit the free-tier monthly bandwidth or concurrent-tunnels cap. Either:

- Reserve a static domain in the ngrok dashboard (paid).
- Use one of the alternatives in section 10.

### Switching between uvicorn and Docker

Port 8000 can only be bound by one process. Stop one before starting the other:

```bash
docker compose stop backend
# …then…
cd backend && source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

ngrok keeps running — it always tunnels to whatever owns `localhost:8000`.

---

## 10. Going to production (replacing ngrok)

ngrok is great for demos and short-lived integrations. For anything that needs
a stable URL, durable uptime, and audit trails, swap it out. The backend +
middleware do not change — only the front door does.

Options (rough order of effort):

| Front door | Effort | Best for |
|---|---|---|
| **Cloudflare Tunnel** (`cloudflared`) | low | Stable HTTPS subdomain, free tier, easy DNS |
| **Tailscale Funnel** | low | If consumers can be Tailscale members |
| **AWS App Runner / GCP Cloud Run** | medium | Hosted serverless container, autoscale |
| **Render / Fly.io / Railway** | medium | PaaS for the whole backend container |
| **EC2 / VM + Nginx + Let's Encrypt** | high | Full control, classic ops |

In every case:

1. The `InboundAPIKeyMiddleware` still enforces `X-API-Key`.
2. The proxy / load balancer adds `X-Forwarded-For`, so the local-exemption
   logic correctly demands a key for external callers.
3. Bind mounts (or named volumes) hold persistent state at
   `backend/data/inbound_api_keys.json` and the other directories.
4. Issuance / revocation still uses `scripts/issue_api_key.py` against the
   same JSON file.

The longer-term roadmap (multi-tenant SaaS shape, rate limiting, scopes-per-route,
audit log retention, etc.) is captured in
[`ENHANCEMENT_HTTPS_EXTERNAL_ACCESS.md`](./ENHANCEMENT_HTTPS_EXTERNAL_ACCESS.md).

---

## Appendix — file map

| Path | Purpose |
|---|---|
| `backend/app/core/security.py` | `InboundAPIKeyMiddleware` |
| `backend/app/services/inbound_api_key_service.py` | JSON-backed key registry |
| `backend/data/inbound_api_keys.json` | Persisted key hashes (gitignored — do not commit) |
| `backend/app/main.py` | Wires middleware + CORS regex for ngrok |
| `scripts/issue_api_key.py` | Admin CLI — issue / list / revoke |
| `scripts/csnp_agent_inline.py` | Partner-ready Python client (inline credentials) |
| `scripts/csnp_agents_cli.py` | Operator CLI (env vars / flags) |
| `scripts/migrate_from_docker_volumes.sh` | One-off helper for moving data from named volumes into the repo bind-mount layout |
| `docker-compose.yml` | Backend service uses repo bind mounts so Docker + native share state |
