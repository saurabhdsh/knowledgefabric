# Cursor Playbook: Mac Bedrock + AWS Bedrock for Any App

Purpose: Give Cursor (or any coding agent) a single instruction set to add **Mac Bedrock** and **AWS Bedrock** LLM support to another application — using the same working pattern as the Weave / Knowledge Fabric platform.

How to use:

1. Open the **other application** in Cursor.
2. Attach or paste this file (or `@` reference it from the Weave repo).
3. Tell Cursor: "Follow `CURSOR_PLAYBOOK_MAC_AWS_BEDROCK.md` and implement Mac Bedrock + AWS Bedrock in this project."

This document is project-agnostic. Adapt folder names (`backend/`, `app/`, `src/`) to the target app.

Reference implementation (Weave):

| File | Role |
|------|------|
| `backend/app/services/llm/bedrock_client.py` | Bedrock Converse via boto3 |
| `backend/app/services/llm/llm_router.py` | Router with OpenAI fallback |
| `backend/app/core/config.py` | `BEDROCK_*`, `AWS_REGION`, provider lists |
| `backend/app/services/api_key_service.py` | Lists providers for UI |
| `docs/MAC_BEDROCK_SETUP.md` | Machine-level Mac Bedrock setup |
| `docs/BEDROCK_INTEGRATION_ANY_PROJECT.md` | Integration patterns |
| `docs/AWS_DEPLOYMENT.md` | AWS hosting + Bedrock IAM |
| `docs/EC2_BEDROCK_DEPLOYMENT_RUNBOOK.md` | EC2 demo with instance role |
| `scripts/deploy-ec2-bedrock.sh` | EC2 + IAM automation example |

---

## 0. Agent mission (read this first)

You are implementing **dual LLM providers** without breaking any existing OpenAI (or other) LLM path:

```text
UI / Agents  →  Backend API  →  LLM Router
                                  ├── bedrock  (default on Mac Bedrock + AWS)
                                  └── openai   (fallback / local without AWS)
```

Success criteria:

- [ ] Backend can call Claude on Amazon Bedrock via Converse API
- [ ] Default provider is configurable (`DEFAULT_LLM_PROVIDER=bedrock`)
- [ ] OpenAI still works when selected or when AWS credentials are missing
- [ ] Frontend can list providers and send `llm_provider` per request
- [ ] Mac uses `~/.aws/credentials`; AWS server uses IAM role (no keys in git)

Do not invent a new model ID. Use the verified values in §1.

---

## 1. Verified working values (copy exactly)

| Setting | Value |
|---------|--------|
| Region | `us-east-1` |
| Model ID (required) | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| Model ID (do not use alone) | `anthropic.claude-sonnet-4-5-20250929-v1:0` |
| IAM actions | `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream` |
| Default provider | `bedrock` |
| Enabled providers | `openai,bedrock` |
| Python SDK | `boto3>=1.34.0` |
| Node SDK | `@aws-sdk/client-bedrock-runtime` |

CLI smoke test that must succeed before coding:

```bash
aws sts get-caller-identity

aws bedrock-runtime converse \
  --model-id "us.anthropic.claude-sonnet-4-5-20250929-v1:0" \
  --messages '[{"role":"user","content":[{"text":"Hi"}]}]' \
  --region us-east-1
```

If this fails, stop and fix IAM / credentials / region before changing application code.

---

## 2. Target `.env` block (add to the other app)

Add to the backend environment file (never commit secrets):

```bash
# --- LLM provider switch ---
DEFAULT_LLM_PROVIDER=bedrock
ENABLED_LLM_PROVIDERS=openai,bedrock

# --- AWS Bedrock ---
BEDROCK_ENABLED=true
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0

# Optional: separate model for ontology / heavy jobs
# BEDROCK_ONTOLOGY_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
# ONTOLOGY_LLM_PROVIDER=bedrock

# --- OpenAI fallback (keep existing if already present) ---
OPENAI_API_KEY=sk-your-key-here
# OPENAI_QUERY_MODEL=gpt-4
```

Notes for Cursor:

- Prefer `~/.aws/credentials` on Mac. Do not put long-lived `AWS_ACCESS_KEY_ID` in git.
- On EC2/ECS, omit access keys entirely — use the instance/task IAM role.
- If the app uses pydantic-settings list parsing, `ENABLED_LLM_PROVIDERS` may need a custom parser for comma-separated strings (Weave does this).

Update `env.example` with the same keys (no real secrets).

---

## 3. Mac Bedrock (laptop / local demo)

### 3.1 One-time machine setup (human or agent with shell access)

1. Install AWS CLI: `brew install awscli`
2. `aws configure` with region `us-east-1`
3. Attach IAM policy to the IAM user (see §5)
4. Run the converse smoke test (§1)
5. Put the `.env` block (§2) into the project

Cursor instructions for Mac:

- Detect whether `~/.aws/credentials` exists; if not, tell the user to run `aws configure`
- In Docker Compose on Mac, either mount `~/.aws:/root/.aws:ro` or pass `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` via env (prefer mount for demo)
- Host-native backend starts (uvicorn/node) already see `~/.aws` — no extra env needed for keys

### 3.2 Docker Compose pattern (Mac)

```yaml
services:
  backend:
    environment:
      - BEDROCK_ENABLED=true
      - DEFAULT_LLM_PROVIDER=bedrock
      - AWS_REGION=us-east-1
      - BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
      - ENABLED_LLM_PROVIDERS=openai,bedrock
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      # Optional if not mounting ~/.aws:
      # - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      # - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
    volumes:
      - ${HOME}/.aws:/root/.aws:ro
```

---

## 4. AWS Bedrock (EC2 / ECS / production)

### 4.1 Authentication model

| Environment | Auth |
|-------------|------|
| Mac Bedrock | IAM user keys in `~/.aws/credentials` |
| EC2 | Instance IAM role (IMDSv2) — no keys in `.env` |
| ECS Fargate | Task IAM role |
| Lambda | Execution role |

### 4.2 IAM policy (attach to user or role)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "*"
    }
  ]
}
```

Name example: `BedrockInvokeAccess` or `WeaveBedrockAccess`.

There is no separate `bedrock:Converse` permission. Converse uses `InvokeModel`.

### 4.3 Production env (server)

```bash
BEDROCK_ENABLED=true
DEFAULT_LLM_PROVIDER=bedrock
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
ENABLED_LLM_PROVIDERS=openai,bedrock
# Do NOT set AWS_ACCESS_KEY_ID on EC2 when using instance role
```

### 4.4 Suggested AWS topology (any app)

Same pattern as Weave:

```text
Internet → DNS → TLS gateway (ALB/Caddy)
  → Frontend (static or container)
  → Backend API
       → DB
       → Amazon Bedrock (IAM role)
```

Minimum go-live checks:

- [ ] Bedrock model available in `us-east-1`
- [ ] Task/instance role has invoke permissions
- [ ] Health endpoint OK
- [ ] Providers API lists `bedrock`
- [ ] One LLM query with `llm_provider=bedrock` succeeds

---

## 5. Code changes Cursor must make

### 5.1 Discover current LLM call sites

Search the target repo:

```bash
rg -n "openai|ChatCompletion|chat\.completions|anthropic|DEFAULT_LLM|llm_provider" --glob '!node_modules' --glob '!.git'
```

List every place that calls an LLM. Plan to route them through one router.

### 5.2 Add dependency

Python:

```txt
boto3>=1.34.0
```

Node:

```bash
npm install @aws-sdk/client-bedrock-runtime
```

### 5.3 Add config settings

Mirror Weave `Settings` fields:

| Name | Type | Default |
|------|------|---------|
| `BEDROCK_ENABLED` | bool | false (or true on AWS compose) |
| `AWS_REGION` | str | `us-east-1` |
| `BEDROCK_MODEL_ID` | str | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| `DEFAULT_LLM_PROVIDER` | str | `openai` locally, `bedrock` on AWS |
| `ENABLED_LLM_PROVIDERS` | list | `openai,bedrock` |

### 5.4 Implement Bedrock client

Create a module equivalent to Weave `bedrock_client.py`:

Required behavior:

1. Create `boto3.client("bedrock-runtime", region_name=AWS_REGION)`
2. Call `converse(...)` with messages
3. Map `system` role to Bedrock `system` blocks; user/assistant to `messages`
4. Resolve model ID: if starts with `anthropic.` and region is `us-*`, prefix `us.`
5. `has_aws_credentials()` via boto3 Session (env, profile, or IAM role)
6. `is_configured()` = enabled + model + region + credentials

Copy logic from Weave:

`Knowledge-Fabric/backend/app/services/llm/bedrock_client.py`

### 5.5 Implement LLM router

Create a module equivalent to Weave `llm_router.py`:

Required behavior:

1. `resolve_provider(optional override)` → ready provider or fallback
2. Prefer Bedrock when configured; fall back to OpenAI on missing AWS credentials
3. Detect credential errors (`Unable to locate credentials`, etc.) and fall back to OpenAI if available
4. `chat_completion(messages, provider=..., model=..., max_tokens=..., temperature=...)`

Copy logic from Weave:

`Knowledge-Fabric/backend/app/services/llm/llm_router.py`

### 5.6 Wire all LLM call sites

Replace direct OpenAI calls with:

```python
from app.services.llm.llm_router import llm_router

text = llm_router.chat_completion(
    provider=request.llm_provider,  # optional
    messages=[{"role": "system", "content": "..."}, {"role": "user", "content": "..."}],
    max_tokens=500,
    temperature=0.3,
)
```

Keep OpenAI SDK installed. Do not delete the OpenAI path.

### 5.7 Providers API (for frontend)

Add something equivalent to:

```http
GET /api/.../providers
```

Response shape:

```json
{
  "providers": [
    { "id": "openai", "name": "OpenAI", "enabled": true, "auth_type": "api_key" },
    { "id": "bedrock", "name": "AWS Bedrock", "enabled": true, "auth_type": "iam", "default_model": "us.anthropic.claude-sonnet-4-5-20250929-v1:0" }
  ],
  "default_provider": "bedrock"
}
```

Only mark providers `enabled` when ready (API key present / Bedrock configured).

### 5.8 Frontend changes

1. Fetch providers from the new API (do not hardcode OpenAI only)
2. Add provider dropdown: OpenAI | AWS Bedrock
3. Send `llm_provider` on query/chat requests
4. Optionally render markdown responses (Claude often returns markdown)

### 5.9 Startup logs

On backend start, log:

```text
Default Provider: bedrock
AWS Bedrock configured (model=us.anthropic..., region=us-east-1)
```

or a clear warning if Bedrock is enabled but credentials are missing (then fall back to OpenAI).

---

## 6. Implementation order for Cursor

Execute in this order; do not skip gates.

| Step | Action | Done when |
|------|--------|-----------|
| 1 | Confirm CLI Bedrock converse works on this machine | Text reply from Claude |
| 2 | Add env vars + `env.example` | File exists, no secrets committed |
| 3 | Add boto3 / AWS SDK | Install succeeds |
| 4 | Add `bedrock_client` | Unit/manual chat returns text |
| 5 | Add `llm_router` | Fallback to OpenAI works without AWS |
| 6 | Route one API endpoint through router | Curl Bedrock + OpenAI both work |
| 7 | Route remaining LLM call sites | No direct OpenAI left in critical paths |
| 8 | Providers endpoint + frontend dropdown | UI lists both |
| 9 | Docker Compose AWS mount / IAM docs | Container or EC2 can call Bedrock |
| 10 | Write short README section for the app | Future agents know the pattern |

---

## 7. Test plan (run after implementation)

```bash
# A. Providers
curl -s http://localhost:<port>/api/.../providers | jq .

# B. Bedrock query
curl -s -X POST http://localhost:<port>/api/.../query \
  -H "Content-Type: application/json" \
  -d '{"query":"Say hello in one sentence","llm_provider":"bedrock"}'

# C. OpenAI query (if key present)
curl -s -X POST http://localhost:<port>/api/.../query \
  -H "Content-Type: application/json" \
  -d '{"query":"Say hello in one sentence","llm_provider":"openai"}'
```

Expected:

- Providers include `bedrock` when `BEDROCK_ENABLED=true` and AWS creds resolve
- Bedrock returns a normal answer
- OpenAI still works when selected
- With Bedrock enabled but no AWS creds, router falls back to OpenAI (if configured) instead of hard-crashing the whole app

---

## 8. Troubleshooting (same as Weave)

| Symptom | Fix |
|---------|-----|
| `ValidationException` on Converse | Use `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| `AccessDeniedException` | Attach InvokeModel IAM policy to user/role |
| `Unable to locate credentials` | Mac: `aws configure`; Docker: mount `~/.aws`; EC2: attach instance role |
| Bedrock missing from provider list | Set `BEDROCK_ENABLED=true`, restart, check credentials probe |
| Default stays openai | Set `DEFAULT_LLM_PROVIDER=bedrock` in `.env`, restart |
| Works in CLI, fails in app | Wrong `AWS_REGION`, or process not inheriting AWS env/profile |
| Works on Mac host, fails in Docker | Mount credentials or pass keys |
| Looking for `bedrock:Converse` in IAM | Wrong — use `InvokeModel` actions only |

---

## 9. Security rules (do not violate)

- Never commit AWS access keys, `.env` with secrets, or PEM files
- Never document real keys in markdown
- Prefer IAM roles on AWS; prefer `~/.aws` on Mac
- Rotate keys if shared carelessly
- Harden `Resource: "*"` to specific model ARNs for production later

---

## 10. Prompt you can paste into Cursor in the other app

```text
Follow the playbook file CURSOR_PLAYBOOK_MAC_AWS_BEDROCK.md (from the Weave docs).

Goal: Add Mac Bedrock + AWS Bedrock to this application exactly like Weave Knowledge Fabric:
- boto3 Bedrock Converse client with us.anthropic.claude-sonnet-4-5-20250929-v1:0
- LLM router that keeps OpenAI and falls back when AWS creds are missing
- Env vars: BEDROCK_ENABLED, AWS_REGION, BEDROCK_MODEL_ID, DEFAULT_LLM_PROVIDER, ENABLED_LLM_PROVIDERS
- Providers API + frontend provider dropdown with llm_provider on requests
- Docker/Compose notes for mounting ~/.aws on Mac
- Document IAM role requirements for EC2/ECS (no keys in production)

Do not remove the existing OpenAI path. Implement non-breaking. Search for all current LLM call sites and route them through the new router. Update env.example. After changes, tell me how to run the CLI smoke test and the curl tests.
```

---

## 11. Related Weave docs (optional deeper reading)

| Doc | Use when |
|-----|----------|
| [MAC_BEDROCK_SETUP.md](./MAC_BEDROCK_SETUP.md) | Setting up a new Mac as a Bedrock machine |
| [BEDROCK_INTEGRATION_ANY_PROJECT.md](./BEDROCK_INTEGRATION_ANY_PROJECT.md) | More code samples (Python + Node) |
| [BEDROCK_SETUP_OTHER_MAC.md](./BEDROCK_SETUP_OTHER_MAC.md) | Full Weave install + Bedrock on another Mac |
| [AWS_DEPLOYMENT.md](./AWS_DEPLOYMENT.md) | ECS/RDS/CloudFront style Weave deploy |
| [EC2_BEDROCK_DEPLOYMENT_RUNBOOK.md](./EC2_BEDROCK_DEPLOYMENT_RUNBOOK.md) | EC2 + Caddy + instance role demo |

---

## 12. Minimal file tree Cursor should create in the other app

```text
your-app/
├── .env / env.example          # Bedrock + OpenAI vars
├── backend/
│   ├── requirements.txt        # boto3>=1.34.0
│   └── .../services/llm/
│       ├── bedrock_client.py   # NEW
│       └── llm_router.py       # NEW
├── frontend/
│   └── ... provider dropdown + llm_provider on API calls
└── docs/
    └── BEDROCK.md              # short app-specific note pointing here
```

---

End of playbook. When both the AWS CLI converse test and an in-app Bedrock query succeed, Mac Bedrock and AWS Bedrock are configured for this application the same way as Weave.
