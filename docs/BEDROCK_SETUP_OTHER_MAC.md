# Weave + AWS Bedrock — Setup on Another Mac

Use this guide to run **Weave (Knowledge Fabric)** on a **new Mac** with **AWS Bedrock** (Claude Sonnet 4.5) and optional **OpenAI** fallback — the same integration we configured in this project.

---

## What you get

| Feature | Works? |
|---------|--------|
| Login (JWT) | Yes |
| Create fabrics / upload PDFs | Yes |
| Test LLM with **Bedrock** | Yes |
| Test LLM with **OpenAI** | Yes (if API key set) |
| LLM Insight / graph insights | Yes |
| EC2 deploy | Optional (see `docs/EC2_DEPLOYMENT.md`) |

---

## Verified working `backend/.env` (copy-paste)

These are the **exact Bedrock + LLM values tested and working** on another Mac:

```bash
# --- Security ---
SECRET_KEY=<openssl rand -hex 32>
ACCESS_TOKEN_EXPIRE_MINUTES=480

# --- LLM provider ---
DEFAULT_LLM_PROVIDER=bedrock
ENABLED_LLM_PROVIDERS=openai,bedrock

# --- AWS Bedrock — Claude Sonnet 4.5 ---
BEDROCK_ENABLED=true
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
BEDROCK_ONTOLOGY_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0

# --- OpenAI (optional fallback) ---
OPENAI_API_KEY=sk-your-key-here
OPENAI_QUERY_MODEL=gpt-4

# --- File uploads (comma-separated, not JSON) ---
ALLOWED_EXTENSIONS=.pdf,.txt,.docx
```

| Key | Working value |
|-----|----------------|
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| `AWS_REGION` | `us-east-1` |
| `DEFAULT_LLM_PROVIDER` | `bedrock` |
| IAM policy actions | `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream` |
| AWS CLI test model | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |

> Do **not** use `anthropic.claude-sonnet-4-5-20250929-v1:0` without the `us.` prefix — it fails with `ValidationException`.

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| **Git** | any | `xcode-select --install` |
| **Python** | **3.10 or 3.11** (not 3.12 alone) | `brew install python@3.11` |
| **Node.js** | 18+ | https://nodejs.org |
| **AWS CLI** | v2 | `brew install awscli` |
| **AWS account** | with Bedrock access | See Part 1 below |

> **Important:** System Python 3.12+ is **not supported** by current dependencies. Always use **3.11** for setup:
> ```bash
> PYTHON_BIN=python3.11 ./setup_without_docker.sh
> ```

---

## Part 1 — AWS setup (one time per account)

### 1.1 Choose region

Use one region everywhere, e.g. **`us-east-1`**.

Bedrock → confirm **Claude Sonnet 4.5** appears in **Model catalog**.

> The old **Model Access** page is retired. Models are enabled by default. For Anthropic, complete the **use case form** once in **Bedrock → Playground** if prompted.

### 1.2 IAM policy (Bedrock)

IAM → **Policies** → **Create policy** → **JSON**:

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

Name: `WeaveBedrockAccess`

> **Note:** There is **no** separate `bedrock:Converse` IAM action. Converse uses `InvokeModel`.

### 1.3 Attach policy to your IAM user

IAM → **Users** → your user (e.g. `SaurabhDubey`) → **Add permissions** → attach `WeaveBedrockAccess`.

If you already have access keys on the Mac, **do not create new keys** — just attach the policy.

### 1.4 Bedrock playground (Anthropic one-time)

1. Bedrock → **Playground** → **Chat**
2. Select **Claude Sonnet 4.5**
3. Submit use case form if asked
4. Send a test message

### 1.5 AWS CLI on the Mac

```bash
aws configure
```

| Prompt | Value |
|--------|--------|
| Access Key ID | your key |
| Secret Access Key | your secret |
| Region | `us-east-1` |
| Output | `json` |

### 1.6 Verify Bedrock from terminal

```bash
aws sts get-caller-identity

aws bedrock-runtime converse \
  --model-id "us.anthropic.claude-sonnet-4-5-20250929-v1:0" \
  --messages '[{"role":"user","content":[{"text":"Hi"}]}]' \
  --region us-east-1
```

If you get a text reply → AWS is ready.

> **Use the `us.` inference profile ID**, not `anthropic.claude-sonnet-4-5-20250929-v1:0` alone. Raw model IDs cause `ValidationException` on Converse.

---

## Part 2 — Clone and install Weave

```bash
cd ~
git clone https://github.com/saurabhdsh/knowledgefabric.git Knowledge-Fabric
cd Knowledge-Fabric
git pull   # always use latest main
```

Install dependencies:

```bash
chmod +x setup_without_docker.sh start_backend.sh start_frontend.sh
PYTHON_BIN=python3.11 ./setup_without_docker.sh
```

First run takes **10–15 minutes**.

---

## Part 3 — Configure `backend/.env`

Weave reads **`backend/.env`** when you run `./start_backend.sh` (not the repo root `.env` unless using Docker).

```bash
cp env.example backend/.env
nano backend/.env
```

### Minimum Bedrock configuration

```bash
# --- Security ---
SECRET_KEY=<long-random-string>
ACCESS_TOKEN_EXPIRE_MINUTES=480

# --- Bedrock (primary) ---
DEFAULT_LLM_PROVIDER=bedrock
BEDROCK_ENABLED=true
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
BEDROCK_ONTOLOGY_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
ENABLED_LLM_PROVIDERS=openai,bedrock

# --- OpenAI (optional fallback) ---
OPENAI_API_KEY=sk-your-key-here
OPENAI_QUERY_MODEL=gpt-4
```

Generate a secret key:

```bash
openssl rand -hex 32
```

### Keep these lines as comma-separated (not JSON)

```bash
ALLOWED_EXTENSIONS=.pdf,.txt,.docx
ENABLED_LLM_PROVIDERS=openai,bedrock
```

The project parses these automatically (do not use JSON arrays in `.env`).

---

## Part 4 — Start Weave

**Terminal 1 — backend:**

```bash
cd ~/Knowledge-Fabric
./start_backend.sh
```

Wait for:

```text
Application startup complete.
API Key Service Status: 2 providers with API keys
Default Provider: bedrock
```

**Terminal 2 — frontend:**

```bash
cd ~/Knowledge-Fabric
./start_frontend.sh
```

**Browser:** http://localhost:3000  
**Login:** `Saurabh` / `admin123`

---

## Part 5 — Verify integration

### 5.1 Provider API

```bash
curl http://localhost:8000/api/v1/knowledge/api-keys/providers
```

Expect **openai** and **bedrock** in `providers`, default `bedrock`.

### 5.2 Test LLM in UI

1. Open **Test LLM**
2. Select a fabric
3. Provider: **AWS Bedrock**
4. Run a query — response should be **formatted** (headings, bullets, bold), not raw `##` or `**`

### 5.3 Sample claims fabric PDF

A sample document for your first fabric:

```
Knowledge-Fabric/sample_data/Weave_Claims_Knowledge_Fabric_Guide.pdf
```

Regenerate if needed:

```bash
cd Knowledge-Fabric/backend
source .venv/bin/activate
pip install fpdf2
python ../sample_data/generate_claims_fabric_pdf.py
```

---

## Part 6 — Docker on Mac (optional)

Native setup (`./start_backend.sh`) is recommended for Bedrock on a Mac because AWS credentials live in `~/.aws/credentials`.

If you use **Docker**, pass AWS credentials into the container.

### Option A — Environment variables in root `.env`

```bash
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
BEDROCK_ENABLED=true
DEFAULT_LLM_PROVIDER=bedrock
OPENAI_API_KEY=sk-...
```

### Option B — Mount AWS profile (add to `docker-compose.yml` backend service)

```yaml
volumes:
  - ~/.aws:/root/.aws:ro
environment:
  - AWS_REGION=us-east-1
  - BEDROCK_ENABLED=true
```

Then:

```bash
docker compose up --build
```

---

## Part 7 — Changes made in this project for Bedrock

When porting Bedrock to **another codebase**, ensure these exist:

| Area | What was added/changed |
|------|-------------------------|
| `backend/app/services/llm/bedrock_client.py` | Bedrock Converse API via boto3 |
| `backend/app/services/llm/llm_router.py` | Routes `openai` \| `bedrock` |
| `backend/app/services/api_key_service.py` | Lists Bedrock as provider (IAM auth) |
| `backend/app/core/config.py` | `BEDROCK_*`, inference profile default, `.env` list parsing |
| `backend/requirements.txt` | `boto3>=1.34.0` |
| `backend/app/models/` | Pydantic models (`knowledge.py`, `ontology.py`) — must be in git |
| `frontend/src/pages/TestLLM.tsx` | Provider dropdown + markdown rendering |
| `frontend/src/utils/renderLlmGraphInsight.tsx` | Formatted LLM output (no raw markdown) |
| `env.example` | Bedrock variables documented |
| `.gitignore` | Must **not** ignore `backend/app/models/` (only `backend/models/` ML weights) |

### Key environment variables

```bash
BEDROCK_ENABLED=true
DEFAULT_LLM_PROVIDER=bedrock
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
ENABLED_LLM_PROVIDERS=openai,bedrock
```

### Inference profile auto-resolve

If `.env` still has the old base model ID:

```bash
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-5-20250929-v1:0
```

The backend auto-maps it to `us.anthropic.claude-sonnet-4-5-20250929-v1:0` for `us-east-1`. Prefer setting the `us.` ID directly.

---

## Part 8 — Troubleshooting

| Problem | Fix |
|---------|-----|
| `No module named app.models` | `git pull` — models package must be in repo; check `.gitignore` |
| `SettingsError` for `ALLOWED_EXTENSIONS` | Update `config.py` or use comma-separated values in `.env`; `git pull` latest |
| `ValidationException` inference profile | Use `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| `AccessDeniedException` | Attach `WeaveBedrockAccess` to IAM user |
| Bedrock not in provider list | `BEDROCK_ENABLED=true`, restart backend |
| Default Provider: openai | Set `DEFAULT_LLM_PROVIDER=bedrock` in `backend/.env`, restart |
| `Address already in use :8000` | `lsof -i :8000` → stop old process or Docker |
| Setup fails on Python 3.12 | Install 3.11: `brew install python@3.11` |
| Raw `##` / `**` in Test LLM | `git pull` for markdown renderer |
| Grey background on responses | `git pull` — dark theme fix in Test LLM |
| Docker Bedrock fails | Pass `AWS_ACCESS_KEY_ID`/`SECRET` or mount `~/.aws` |

---

## Part 9 — Quick checklist (print this)

- [ ] IAM policy `WeaveBedrockAccess` attached to user
- [ ] `aws configure` done on Mac
- [ ] Bedrock CLI test works with `us.anthropic...` model ID
- [ ] Repo cloned, `git pull` latest
- [ ] `PYTHON_BIN=python3.11 ./setup_without_docker.sh` completed
- [ ] `backend/.env` created with Bedrock settings
- [ ] `./start_backend.sh` shows **2 providers**, default **bedrock**
- [ ] `./start_frontend.sh` running
- [ ] Login works at http://localhost:3000
- [ ] Test LLM query succeeds with Bedrock

---

## Part 10 — Switching providers

| Goal | Setting |
|------|---------|
| Default Bedrock | `DEFAULT_LLM_PROVIDER=bedrock` |
| Default OpenAI | `DEFAULT_LLM_PROVIDER=openai` + `OPENAI_API_KEY` |
| Per query in UI | Test LLM → dropdown OpenAI / AWS Bedrock |
| Ontology jobs on Bedrock | `ONTOLOGY_LLM_PROVIDER=bedrock` |

Both providers can stay enabled:

```bash
ENABLED_LLM_PROVIDERS=openai,bedrock
```

---

## Related docs

- [EC2_DEPLOYMENT.md](./EC2_DEPLOYMENT.md) — public URL on one EC2 instance
- [AWS_DEPLOYMENT.md](./AWS_DEPLOYMENT.md) — full AWS architecture (ECS, RDS, etc.)
- [env.example](../env.example) — all environment variables

---

## Support commands

```bash
# Backend health
curl http://localhost:8000/health

# Providers
curl http://localhost:8000/api/v1/knowledge/api-keys/providers

# Python version in venv
Knowledge-Fabric/backend/.venv/bin/python --version

# Latest code
cd Knowledge-Fabric && git pull && ./start_backend.sh
```

---

*Last updated: matches Weave main branch with Bedrock + Claude Sonnet 4.5 inference profile integration.*
