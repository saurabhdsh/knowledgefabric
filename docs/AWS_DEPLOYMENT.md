# Weave on AWS — Deployment & Bedrock Guide

This guide covers hosting Weave (Knowledge Fabric) on AWS and switching LLM calls to **Amazon Bedrock** without breaking the existing OpenAI setup.

---

## Architecture (recommended)

```text
Internet
   │
   ▼
Route 53 ──► CloudFront (React static build)
   │
   └──► ALB ──► ECS Fargate (backend API :8000)
                    │
        ┌───────────┼───────────────┐
        ▼           ▼               ▼
     RDS Postgres   EFS volumes   Amazon Bedrock
     (metadata)    (uploads,      (Claude / etc.)
                    chroma, data)
```

| Component | AWS service | Notes |
|-----------|-------------|--------|
| Frontend | S3 + CloudFront | `npm run build` → static assets |
| Backend API | ECS Fargate or EC2 | Docker image from `backend/Dockerfile` |
| Database | RDS PostgreSQL 15 | Same schema as local Docker Compose |
| Persistent files | EFS mount | `uploads/`, `chroma_db/`, `data/`, `ontology_data/` |
| Secrets | Secrets Manager | `SECRET_KEY`, DB password, optional `OPENAI_API_KEY` |
| LLM | **Bedrock** | IAM role — no API key in env |
| TLS | ACM certificate | On ALB + CloudFront |

---

## Step 1 — Build & push backend image

```bash
cd Knowledge-Fabric/backend
docker build -t weave-backend:latest .

# ECR example
aws ecr create-repository --repository-name weave-backend
docker tag weave-backend:latest <account>.dkr.ecr.<region>.amazonaws.com/weave-backend:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/weave-backend:latest
```

Frontend:

```bash
cd Knowledge-Fabric/frontend
REACT_APP_API_URL=https://api.your-domain.com npm run build
aws s3 sync build/ s3://your-weave-frontend-bucket/
```

---

## Step 2 — RDS PostgreSQL

Create RDS PostgreSQL 15 and set:

```bash
DATABASE_URL=postgresql://weave_user:<password>@<rds-endpoint>:5432/weave
```

Run migrations on first boot (Weave calls `init_db()` at startup).

---

## Step 3 — EFS for stateful data

Mount EFS to the backend container:

| Container path | Purpose |
|----------------|---------|
| `/app/uploads` | PDF / document uploads |
| `/app/chroma_db` | Vector index |
| `/app/data` | Platform SQLite fallback, JSON backups |
| `/app/ontology_data` | Ontology projects |

Set env vars (already supported):

```bash
KF_UPLOAD_DIR=/app/uploads
KF_CHROMA_DIR=/app/chroma_db
KF_DATA_DIR=/app/data
KF_ONTOLOGY_DATA_DIR=/app/ontology_data
```

---

## Step 4 — ECS task environment

Minimum production env:

```bash
# Core
SECRET_KEY=<from-secrets-manager>
DATABASE_URL=postgresql://...
HOST=0.0.0.0
PORT=8000

# Auth (JWT login)
ACCESS_TOKEN_EXPIRE_MINUTES=480

# CORS — your CloudFront / domain
KF_CORS_ORIGINS=https://weave.your-domain.com

# LLM — Bedrock on AWS (recommended)
BEDROCK_ENABLED=true
DEFAULT_LLM_PROVIDER=bedrock
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-5-20250929-v1:0
ENABLED_LLM_PROVIDERS=openai,bedrock

# Optional: keep OpenAI for local/dev fallback
# OPENAI_API_KEY=sk-...
# DEFAULT_LLM_PROVIDER=openai
```

Frontend task / build arg:

```bash
REACT_APP_API_URL=https://api.your-domain.com
```

---

## Step 5 — IAM policy for Bedrock

Attach to the **ECS task role** (not the execution role):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:Converse",
        "bedrock:ConverseStream"
      ],
      "Resource": "*"
    }
  ]
}
```

In Bedrock console → **Model access**, enable the models you use (e.g. Claude 3.5 Sonnet).

No `OPENAI_API_KEY` is required when `DEFAULT_LLM_PROVIDER=bedrock`.

---

## Step 6 — ALB & health checks

- Target group → backend port **8000**
- Health check path: **`/health`**
- Idle timeout: ≥ 120s (fabric creation / ontology jobs)

---

## Bedrock vs OpenAI (non-breaking)

Weave uses an **LLM router** (`app/services/llm/llm_router.py`):

| Provider | When to use | Auth |
|----------|-------------|------|
| `openai` | Local dev, BYOK partners | `OPENAI_API_KEY` or `X-LLM-API-Key` header |
| `bedrock` | AWS production | IAM role on ECS/EC2/Lambda |

### Switch default to Bedrock (AWS only)

```bash
BEDROCK_ENABLED=true
DEFAULT_LLM_PROVIDER=bedrock
```

Existing OpenAI flow continues to work if you keep `OPENAI_API_KEY` and set `DEFAULT_LLM_PROVIDER=openai`.

### Per-request provider (Test LLM / API)

```bash
POST /api/v1/knowledge/query/{fabric_id}
{
  "query": "...",
  "llm_provider": "bedrock"
}
```

### Ontology / discovery on Bedrock

```bash
ONTOLOGY_LLM_PROVIDER=bedrock
BEDROCK_ONTOLOGY_MODEL_ID=anthropic.claude-sonnet-4-5-20250929-v1:0
```

---

## Docker Compose (hybrid local test)

To test Bedrock locally with AWS credentials:

```bash
export AWS_PROFILE=your-profile
export AWS_REGION=us-east-1
export BEDROCK_ENABLED=true
export DEFAULT_LLM_PROVIDER=bedrock
docker compose up --build
```

---

## Checklist before go-live

- [ ] RDS PostgreSQL reachable from ECS security group
- [ ] EFS mounted; data survives task restarts
- [ ] `SECRET_KEY` rotated (not default)
- [ ] HTTPS on ALB + CloudFront
- [ ] Bedrock model access enabled in account/region
- [ ] ECS task role has Bedrock invoke permissions
- [ ] `GET /health` returns healthy
- [ ] Login works (`/api/v1/auth/login`)
- [ ] `GET /api/v1/knowledge/api-keys/providers` lists `bedrock`

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Bedrock not in provider list | Set `BEDROCK_ENABLED=true`, `ENABLED_LLM_PROVIDERS=openai,bedrock` |
| `AccessDeniedException` on query | Add Bedrock IAM policy to task role; enable model access |
| Empty LLM response | Verify `BEDROCK_MODEL_ID` matches an enabled model in your region |
| CORS errors from browser | Set `KF_CORS_ORIGINS` to your frontend URL |
| Fabrics missing after deploy | Ensure EFS paths match env vars; run legacy migration on first boot |

---

## Cost notes

- **Fargate**: pay per vCPU/GB-hour; size for Chroma + embedding workload (≥ 4 GB RAM recommended).
- **Bedrock**: pay per input/output token; no OpenAI egress.
- **EFS**: pay for storage + throughput; use Infrequent Access for old uploads if needed.

For TCS enterprise deployments, consider a dedicated VPC, private subnets for RDS/EFS, and AWS WAF on the ALB.
