# Mac Bedrock Setup

Reusable runbook to configure a **Mac Bedrock** machine: AWS credentials + Claude on Bedrock work from Terminal, then any agentic project can use the same stack.

Use this when you want another Mac to match the working **Mac Bedrock** setup used for Weave demos.

---

## What “Mac Bedrock” means

| Label | Meaning |
|-------|---------|
| **Mac Bedrock** | Mac with valid AWS credentials, Bedrock IAM access, and apps defaulting to Bedrock |
| **EC2 Bedrock** | Server uses an **IAM instance role** (no access keys on disk) |

```text
Mac Bedrock
  ~/.aws/credentials  ──►  boto3 / AWS CLI  ──►  Amazon Bedrock (Claude)
  Project .env        ──►  DEFAULT_LLM_PROVIDER=bedrock
```

Once the Mac is set up, **every new agentic project** only needs the env vars and an SDK client — not a new IAM setup (same AWS user/policy).

---

## Verified working values (copy these)

| Item | Value |
|------|--------|
| Region | `us-east-1` |
| Model / inference profile | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| IAM actions | `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream` |
| IAM policy name (example) | `WeaveBedrockAccess` |
| Default provider | `bedrock` |
| Optional fallback | OpenAI via `OPENAI_API_KEY` |

**Do not use** the bare foundation ID alone:

```text
anthropic.claude-sonnet-4-5-20250929-v1:0   ❌ ValidationException on Converse
us.anthropic.claude-sonnet-4-5-20250929-v1:0  ✅ works
```

---

## Part 1 — One-time AWS account setup

Do this once per AWS account (reuse across Macs and projects).

### 1.1 Region

Console top-right → **US East (N. Virginia) `us-east-1`**. Use the same region for CLI, `.env`, and Bedrock.

### 1.2 Enable Claude on Bedrock

1. Open **Amazon Bedrock** → **Model catalog**
2. Confirm **Claude Sonnet 4.5** is available
3. **Playground** → **Chat** → pick Claude Sonnet 4.5
4. Complete the Anthropic **use case form** if prompted
5. Send a short test message in the playground

### 1.3 IAM policy

**IAM** → **Policies** → **Create policy** → JSON:

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

Name it e.g. `WeaveBedrockAccess` or `BedrockInvokeAccess`.

> There is **no** separate `bedrock:Converse` permission. Converse uses `InvokeModel`.

### 1.4 Attach policy to the IAM user

**IAM** → **Users** → your user (e.g. `SaurabhDubey`) → **Add permissions** → attach the policy above.

If this Mac already has working access keys for that user, **do not create new keys** — only attach the policy.

---

## Part 2 — Configure Mac Bedrock

### 2.1 Install tools

```bash
# AWS CLI v2
brew install awscli

# Optional but useful for Python agent backends
brew install python@3.11
```

Check:

```bash
aws --version
python3.11 --version   # if using Python agents
```

### 2.2 Configure credentials

```bash
aws configure
```

| Prompt | Value |
|--------|--------|
| AWS Access Key ID | from IAM user |
| AWS Secret Access Key | from IAM user |
| Default region | `us-east-1` |
| Default output format | `json` |

This writes:

- `~/.aws/credentials`
- `~/.aws/config`

boto3 and the AWS SDK pick these up automatically for any project on this Mac.

### 2.3 Prove Bedrock works (required gate)

```bash
aws sts get-caller-identity
```

Expect your account and IAM user ARN.

Then:

```bash
aws bedrock-runtime converse \
  --model-id "us.anthropic.claude-sonnet-4-5-20250929-v1:0" \
  --messages '[{"role":"user","content":[{"text":"Hi"}]}]' \
  --region us-east-1
```

If you get a text reply → **Mac Bedrock is ready**. Reuse this machine for every project.

### 2.4 Optional: named profile

If you use multiple AWS accounts:

```bash
aws configure --profile mac-bedrock
export AWS_PROFILE=mac-bedrock
```

Put `AWS_PROFILE=mac-bedrock` in each project’s shell / `.env` loader if needed.

---

## Part 3 — Wire any new agentic project

Same Mac credentials; only project config changes.

### 3.1 Standard `.env` block

```bash
# --- Mac Bedrock ---
DEFAULT_LLM_PROVIDER=bedrock
ENABLED_LLM_PROVIDERS=openai,bedrock

BEDROCK_ENABLED=true
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0

# Optional OpenAI fallback
OPENAI_API_KEY=sk-your-key-here
OPENAI_QUERY_MODEL=gpt-4
```

Do **not** put long-lived AWS access keys in git. Prefer `~/.aws/credentials` on the Mac Bedrock machine.

### 3.2 Python (boto3)

```bash
pip install "boto3>=1.34.0"
```

```python
import boto3

client = boto3.client("bedrock-runtime", region_name="us-east-1")
resp = client.converse(
    modelId="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    messages=[{"role": "user", "content": [{"text": "Hello"}]}],
)
print(resp["output"]["message"]["content"][0]["text"])
```

### 3.3 Node.js

```bash
npm install @aws-sdk/client-bedrock-runtime
```

```js
import { BedrockRuntimeClient, ConverseCommand } from "@aws-sdk/client-bedrock-runtime";

const client = new BedrockRuntimeClient({ region: "us-east-1" });
const out = await client.send(new ConverseCommand({
  modelId: "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
  messages: [{ role: "user", content: [{ text: "Hello" }] }],
}));
console.log(out.output.message.content[0].text);
```

### 3.4 Recommended app pattern

```text
Agent / UI  →  your backend  →  LLM router
                                  ├── bedrock (default on Mac Bedrock)
                                  └── openai  (fallback / secondary)
```

- Default from `DEFAULT_LLM_PROVIDER`
- Allow per-request override (`llm_provider=bedrock|openai`)

### 3.5 Docker on Mac Bedrock

Processes started on the host already see `~/.aws`. Containers need credentials passed in:

**Option A — env vars:**

```bash
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
```

**Option B — mount profile:**

```yaml
volumes:
  - ~/.aws:/root/.aws:ro
environment:
  - AWS_REGION=us-east-1
  - AWS_PROFILE=default
```

---

## Part 4 — Checklist (clone this setup)

For a new machine labeled **Mac Bedrock**:

- [ ] Same AWS account + region `us-east-1`
- [ ] IAM policy attached to the IAM user
- [ ] `brew install awscli` (and Python 3.11 if needed)
- [ ] `aws configure` with existing keys (or new keys for a new IAM user)
- [ ] `aws sts get-caller-identity` succeeds
- [ ] `aws bedrock-runtime converse ... us.anthropic...` returns text
- [ ] New project `.env` uses the verified Bedrock block above
- [ ] App starts with default provider **bedrock**

---

## Part 5 — Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Unable to locate credentials` | Run `aws configure` on that Mac; restart the app |
| `AccessDeniedException` | Attach Bedrock invoke policy to the IAM user |
| `ValidationException` / inference profile | Use `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| `SignatureDoesNotMatch` | Wrong/rotated secret — create new access key or fix clock |
| Works in CLI, fails in Docker | Mount `~/.aws` or pass `AWS_ACCESS_KEY_ID` / `SECRET` |
| Works on Mac A, fails on Mac B | Mac B missing `aws configure` or policy on that user’s keys |

---

## Part 6 — Security notes

- On Mac Bedrock, use IAM user credentials via `~/.aws`. On EC2, prefer an **instance role**.
- Never commit access keys, `.env` secrets, or `~/.aws/credentials`.
- Rotate keys if a machine leaves the team or keys leak.
- Scope production IAM `Resource` to specific model ARNs when you harden beyond demos.

---

## Related docs in this repo

| Doc | When to use |
|-----|-------------|
| [MAC_BEDROCK_SETUP.md](./MAC_BEDROCK_SETUP.md) | **This file** — configure Mac Bedrock |
| [BEDROCK_INTEGRATION_ANY_PROJECT.md](./BEDROCK_INTEGRATION_ANY_PROJECT.md) | Add Bedrock + router code to a new app |
| [BEDROCK_SETUP_OTHER_MAC.md](./BEDROCK_SETUP_OTHER_MAC.md) | Full Weave install on Mac Bedrock |
| [EC2_BEDROCK_DEPLOYMENT_RUNBOOK.md](./EC2_BEDROCK_DEPLOYMENT_RUNBOOK.md) | Host Weave on EC2 with Bedrock + domain |

---

## Quick reference card

```bash
# Identity
aws sts get-caller-identity

# Bedrock smoke test
aws bedrock-runtime converse \
  --model-id "us.anthropic.claude-sonnet-4-5-20250929-v1:0" \
  --messages '[{"role":"user","content":[{"text":"Hi"}]}]' \
  --region us-east-1

# Project env (minimum)
# BEDROCK_ENABLED=true
# DEFAULT_LLM_PROVIDER=bedrock
# AWS_REGION=us-east-1
# BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
```

When both commands succeed, the machine is **Mac Bedrock** and ready for the next agentic project.
