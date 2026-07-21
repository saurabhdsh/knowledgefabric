# Add AWS Bedrock to Any Backend + Frontend Project

Use this guide when you have an **existing project** (any stack) with a backend API and frontend UI that already uses **OpenAI or another LLM** — and you want to add **AWS Bedrock** without breaking the current setup.

This is **project-agnostic**. Adapt file names and frameworks to your codebase.

> **Mac first:** To turn a laptop into a reusable **Mac Bedrock** machine (AWS CLI, IAM, smoke test), start with [MAC_BEDROCK_SETUP.md](./MAC_BEDROCK_SETUP.md), then return here for app code.

---

## Verified working values (tested on Mac, `us-east-1`)

Copy this block into your backend `.env` — these are the **exact values that worked** on another Mac with Bedrock + OpenAI both enabled:

```bash
# --- LLM provider ---
DEFAULT_LLM_PROVIDER=bedrock
ENABLED_LLM_PROVIDERS=openai,bedrock

# --- AWS Bedrock (Claude Sonnet 4.5) ---
BEDROCK_ENABLED=true
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
BEDROCK_ONTOLOGY_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0

# --- OpenAI (optional — keep for fallback) ---
OPENAI_API_KEY=sk-your-key-here
OPENAI_QUERY_MODEL=gpt-4
```

| Setting | Working value | Notes |
|---------|---------------|--------|
| **Model (use this)** | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` | US inference profile — **required** |
| **Model (do not use)** | `anthropic.claude-sonnet-4-5-20250929-v1:0` | Causes `ValidationException` on Converse |
| **Region** | `us-east-1` | Must match Bedrock console region |
| **Default provider** | `bedrock` | Backend logs: `Default Provider: bedrock` |
| **IAM user** | e.g. `SaurabhDubey` | Policy: `InvokeModel` + `InvokeModelWithResponseStream` |
| **Python** | `3.11` | Use `PYTHON_BIN=python3.11` if system is 3.12+ |

**CLI test that confirmed Bedrock (run before backend start):**

```bash
aws configure   # region: us-east-1

aws bedrock-runtime converse \
  --model-id "us.anthropic.claude-sonnet-4-5-20250929-v1:0" \
  --messages '[{"role":"user","content":[{"text":"Hi"}]}]' \
  --region us-east-1
```

**Optional inference profiles (same model, different routing):**

```bash
# US regional (recommended — what we used)
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0

# Global (higher availability, AWS routes automatically)
# BEDROCK_MODEL_ID=global.anthropic.claude-sonnet-4-5-20250929-v1:0
```

**Backend startup should show:**

```text
API Key Service Status: 2 providers with API keys
Default Provider: bedrock
```

---

## Goal

```text
Before                          After
──────                          ─────
Frontend ──► Backend ──► OpenAI     Frontend ──► Backend ──► LLM Router ──┬──► OpenAI
                                                                          └──► AWS Bedrock
```

- **OpenAI** keeps working (API key in `.env`)
- **Bedrock** uses AWS IAM (no API key in production)
- Switch provider via **environment variable** or **per-request** from the UI

---

## Part 1 — AWS setup (same for every project)

### 1.1 IAM policy

Create policy `BedrockInvokeAccess`:

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

Attach to:
- **Local dev:** your IAM **user**
- **EC2/ECS/Lambda:** the **instance/task role**

> There is no separate `bedrock:Converse` IAM permission. The Converse API uses `InvokeModel`.

### 1.2 Bedrock model

1. Pick a region (e.g. `us-east-1`)
2. Bedrock → **Model catalog** → enable **Claude Sonnet 4.5** (or your model)
3. **Playground** → submit Anthropic use case form once if prompted

### 1.3 Model ID — use inference profile

For Claude 4.5 in US regions, use:

```bash
us.anthropic.claude-sonnet-4-5-20250929-v1:0
```

**Not** the raw foundation model ID alone — it causes `ValidationException` on Converse.

### 1.4 Local AWS credentials

```bash
aws configure
aws sts get-caller-identity

aws bedrock-runtime converse \
  --model-id "us.anthropic.claude-sonnet-4-5-20250929-v1:0" \
  --messages '[{"role":"user","content":[{"text":"Hello"}]}]' \
  --region us-east-1
```

If this works, any backend using boto3 can call Bedrock.

---

## Part 2 — Backend changes (pattern)

### 2.1 Add dependency

**Python:**

```txt
boto3>=1.34.0
```

**Node.js:**

```bash
npm install @aws-sdk/client-bedrock-runtime
```

### 2.2 Environment variables

Add to `.env` (never commit secrets):

```bash
# Provider switch
DEFAULT_LLM_PROVIDER=bedrock          # or openai
ENABLED_LLM_PROVIDERS=openai,bedrock

# Bedrock
BEDROCK_ENABLED=true
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0

# OpenAI (keep existing)
OPENAI_API_KEY=sk-...
```

| Variable | Purpose |
|----------|---------|
| `DEFAULT_LLM_PROVIDER` | Default when client does not specify |
| `BEDROCK_ENABLED` | Feature flag for Bedrock |
| `BEDROCK_MODEL_ID` | Inference profile or model ID |
| `AWS_REGION` | Must match Bedrock region |
| `OPENAI_API_KEY` | Unchanged — OpenAI still works |

### 2.3 Bedrock client (Python example)

Create `services/llm/bedrock_client.py`:

```python
import boto3
from typing import List, Dict, Optional

class BedrockClient:
    def __init__(self, region: str, model_id: str):
        self._region = region
        self._model_id = model_id
        self._runtime = None

    def _client(self):
        if self._runtime is None:
            self._runtime = boto3.client("bedrock-runtime", region_name=self._region)
        return self._runtime

    def _resolve_model_id(self, model_id: str) -> str:
        """Map anthropic.* to us.anthropic.* for US regions."""
        if model_id.startswith(("us.", "eu.", "global.", "au.", "jp.")):
            return model_id
        if model_id.startswith("anthropic.") and self._region.startswith("us-"):
            return f"us.{model_id}"
        return model_id

    def chat(self, messages: List[Dict[str, str]], *, max_tokens: int = 500, temperature: float = 0.3) -> str:
        model_id = self._resolve_model_id(self._model_id)
        system, converse_msgs = [], []
        for m in messages:
            role = (m.get("role") or "user").lower()
            content = (m.get("content") or "").strip()
            if not content:
                continue
            if role == "system":
                system.append({"text": content})
            else:
                converse_msgs.append({
                    "role": "assistant" if role == "assistant" else "user",
                    "content": [{"text": content}],
                })
        kwargs = {
            "modelId": model_id,
            "messages": converse_msgs,
            "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
        }
        if system:
            kwargs["system"] = system
        resp = self._client().converse(**kwargs)
        parts = resp["output"]["message"]["content"]
        return "\n".join(p["text"] for p in parts if p.get("text")).strip()
```

### 2.4 LLM router (do not replace OpenAI — wrap it)

Create `services/llm/llm_router.py`:

```python
class LLMRouter:
    def __init__(self, openai_client, bedrock_client, default_provider: str):
        self.openai = openai_client
        self.bedrock = bedrock_client
        self.default = default_provider

    def chat(self, messages, *, provider=None, **kwargs) -> str:
        chosen = (provider or self.default).lower()
        if chosen == "bedrock":
            return self.bedrock.chat(messages, **kwargs)
        if chosen == "openai":
            return self.openai.chat(messages, **kwargs)  # your existing method
        raise ValueError(f"Unknown provider: {chosen}")
```

### 2.5 Replace direct OpenAI calls

**Before (scattered in codebase):**

```python
openai.ChatCompletion.create(model="gpt-4", messages=messages)
```

**After (one entry point):**

```python
llm_router.chat(messages, provider=request.llm_provider)  # optional per-request
```

Search your project for all LLM call sites:

```bash
rg "openai\.|ChatCompletion|chat\.completions" backend/
```

Update each to use the router.

### 2.6 API contract (add optional provider field)

```json
POST /api/query
{
  "query": "Explain duplicate claim detection",
  "llm_provider": "bedrock"
}
```

If `llm_provider` is omitted → use `DEFAULT_LLM_PROVIDER`.

### 2.7 Providers endpoint (for frontend dropdown)

```json
GET /api/llm/providers

{
  "providers": [
    { "id": "openai", "name": "OpenAI", "auth_type": "api_key" },
    { "id": "bedrock", "name": "AWS Bedrock", "auth_type": "iam" }
  ],
  "default_provider": "bedrock"
}
```

Only list providers that pass a readiness check (API key present / Bedrock enabled).

---

## Part 3 — Frontend changes (pattern)

### 3.1 Load providers from API

```typescript
const res = await fetch('/api/llm/providers');
const { providers, default_provider } = await res.json();
```

Populate a dropdown — do not hardcode OpenAI only.

### 3.2 Send provider with each request

```typescript
await fetch('/api/query', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: userQuery,
    llm_provider: selectedProvider,  // 'bedrock' | 'openai'
  }),
});
```

### 3.3 Render markdown responses

LLMs return `##`, `**`, bullets. Do not show raw markdown.

Options:
- Use `react-markdown` library
- Or a small custom renderer (headings, lists, bold, code)

Without this, users see ugly `**bold**` and `## Heading` text.

---

## Part 4 — Deployment matrix

| Environment | OpenAI | Bedrock |
|-------------|--------|---------|
| **Local Mac** | `OPENAI_API_KEY` in `.env` | `aws configure` / env vars |
| **Docker local** | `OPENAI_API_KEY` in compose `.env` | Mount `~/.aws` or pass `AWS_ACCESS_KEY_ID` |
| **EC2** | `OPENAI_API_KEY` in `.env` or Secrets Manager | IAM **instance role** |
| **ECS/Fargate** | Secrets Manager | IAM **task role** |
| **Lambda** | Env var / Secrets Manager | Lambda **execution role** |

**Production best practice:** Bedrock via IAM role, no long-lived AWS keys in `.env`.

---

## Part 5 — Non-breaking migration checklist

Use this when adding Bedrock to a live project:

- [ ] Add `boto3` / AWS SDK — do not remove OpenAI SDK
- [ ] Add Bedrock env vars with `BEDROCK_ENABLED=false` default
- [ ] Create `bedrock_client` + `llm_router` — do not delete OpenAI code yet
- [ ] Route **one** endpoint through router; test Bedrock
- [ ] Route remaining LLM call sites one by one
- [ ] Add `GET /llm/providers` for frontend
- [ ] Add provider dropdown in UI
- [ ] Test OpenAI still works with `DEFAULT_LLM_PROVIDER=openai`
- [ ] Test Bedrock with `DEFAULT_LLM_PROVIDER=bedrock`
- [ ] Deploy with IAM role on AWS; keep OpenAI key as fallback if needed

---

## Part 6 — Minimal file structure to add

```text
your-project/
├── backend/
│   ├── .env                          # add BEDROCK_* vars
│   ├── requirements.txt              # add boto3
│   └── app/
│       └── services/
│           └── llm/
│               ├── __init__.py
│               ├── bedrock_client.py  # NEW
│               ├── llm_router.py      # NEW
│               └── openai_client.py   # existing or extracted
├── frontend/
│   └── src/
│       ├── api/llm.ts                 # provider + query calls
│       └── components/
│           └── LlmProviderSelect.tsx  # NEW dropdown
└── docs/
    └── BEDROCK_INTEGRATION.md         # this file
```

---

## Part 7 — Node.js backend example (Express)

```javascript
import { BedrockRuntimeClient, ConverseCommand } from "@aws-sdk/client-bedrock-runtime";

const bedrock = new BedrockRuntimeClient({ region: process.env.AWS_REGION });

async function bedrockChat(messages, modelId) {
  const cmd = new ConverseCommand({
    modelId: modelId.startsWith("us.") ? modelId : `us.${modelId}`,
    messages: messages.map(m => ({
      role: m.role === "assistant" ? "assistant" : "user",
      content: [{ text: m.content }],
    })),
    inferenceConfig: { maxTokens: 500, temperature: 0.3 },
  });
  const res = await bedrock.send(cmd);
  return res.output.message.content.map(c => c.text).join("\n");
}

// Router
async function llmChat(messages, provider = process.env.DEFAULT_LLM_PROVIDER) {
  if (provider === "bedrock") return bedrockChat(messages, process.env.BEDROCK_MODEL_ID);
  if (provider === "openai") return openaiChat(messages);  // existing
  throw new Error(`Unknown provider: ${provider}`);
}
```

---

## Part 8 — Common mistakes

| Mistake | Fix |
|---------|-----|
| Using `anthropic.claude-...` without `us.` prefix | Use inference profile ID |
| Looking for `bedrock:Converse` in IAM | Use `bedrock:InvokeModel` |
| Bedrock fails in Docker | Pass AWS creds or mount `~/.aws` |
| Removing OpenAI when adding Bedrock | Keep both; use router |
| Hardcoding provider in frontend | Load from `/llm/providers` API |
| Raw markdown in UI | Add markdown renderer |
| `.env` list fields as JSON | Use comma-separated or proper parser |
| Gitignoring `app/models/` folder | Only ignore ML weight dirs like `backend/models/` |

---

## Part 9 — Testing

```bash
# 1. AWS CLI
aws bedrock-runtime converse --model-id "us.anthropic.claude-sonnet-4-5-20250929-v1:0" \
  --messages '[{"role":"user","content":[{"text":"Hi"}]}]' --region us-east-1

# 2. Backend providers endpoint
curl http://localhost:8000/api/llm/providers

# 3. Bedrock query
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query":"Hello","llm_provider":"bedrock"}'

# 4. OpenAI still works
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query":"Hello","llm_provider":"openai"}'
```

---

## Part 10 — When to use Bedrock vs OpenAI

| Use Bedrock | Use OpenAI |
|-------------|------------|
| AWS production (EC2, ECS, Lambda) | Local dev without AWS |
| Enterprise / no external API keys | Specific OpenAI-only models |
| Claude via AWS contract | GPT-4o features not on Bedrock |
| IAM-based security | BYOK partner integrations |

You can run **both** and switch with one env var:

```bash
DEFAULT_LLM_PROVIDER=bedrock   # production
DEFAULT_LLM_PROVIDER=openai    # local fallback
```

---

## Summary — 10 steps for any project

1. Create IAM policy + attach to user/role  
2. Verify Bedrock CLI with `us.anthropic...` model ID  
3. Add `boto3` / AWS SDK to backend  
4. Add Bedrock env vars (keep OpenAI vars)  
5. Implement `bedrock_client` + `llm_router`  
6. Replace direct OpenAI calls with router  
7. Add `llm_provider` to API requests  
8. Expose `GET /llm/providers`  
9. Frontend: provider dropdown + markdown rendering  
10. Test both providers; deploy with IAM role on AWS  

---

*Generic integration guide — apply to any backend + frontend stack. For a full worked example in this repo, see `docs/BEDROCK_SETUP_OTHER_MAC.md` (Weave-specific setup).*
