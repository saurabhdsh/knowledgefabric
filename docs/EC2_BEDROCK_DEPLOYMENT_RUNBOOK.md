# Weave EC2 + Bedrock Deployment Runbook

Last updated: 18 July 2026

This document consolidates the AWS infrastructure, Weave deployment, Amazon
Bedrock integration, public URL, custom domain, fixes, and operational commands
used for the Weave customer-demo environment.

Do not add AWS access keys, secret keys, `.env` contents, or PEM contents to
this document or to Git.

---

## 1. Deployment Summary

| Item | Current value |
|---|---|
| Application | TCS Weave / Knowledge Fabric |
| AWS region | `us-east-1` |
| EC2 name | `weave-server` |
| Instance type | `t3.large` (2 vCPU, 8 GB RAM) |
| Root storage | 50 GB encrypted gp3 |
| Swap | 4 GB |
| Operating system | Amazon Linux 2023 |
| Elastic IP | `52.0.130.62` |
| Temporary URL | `http://52.0.130.62` |
| Custom domain | `cuweave.com` |
| WWW domain | `www.cuweave.com` |
| LLM provider | Amazon Bedrock |
| Bedrock region | `us-east-1` |
| Bedrock model | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| Deployment runtime | Docker Compose |
| Database | PostgreSQL 15 container |
| HTTPS gateway | Caddy + Let's Encrypt |

This is a demo deployment intended for approximately 1-15 users. Start with
`t3.large`; move to `t3.xlarge` only if concurrent ontology, ingestion, or
codebase-analysis jobs exhaust memory.

---

## 2. Architecture

```text
Internet
   |
   v
GoDaddy DNS
cuweave.com / www.cuweave.com
   |
   v
Elastic IP: 52.0.130.62
   |
   v
Caddy :80 / :443
  - HTTP to HTTPS redirect
  - Let's Encrypt certificate and renewal
   |
   v
Weave nginx web container :80
  - React application
  - /api/* proxy
   |
   v
FastAPI backend :8000
  |        |             |
  v        v             v
Postgres  ChromaDB    Amazon Bedrock
                         ^
                         |
               EC2 IAM instance role
```

AWS credentials are not copied into EC2 or Docker. The backend receives
temporary Bedrock credentials through the EC2 IAM instance role and Instance
Metadata Service (IMDSv2).

---

## 3. AWS Resources

### IAM policy

Name:

```text
WeaveBedrockAccess
```

Permissions:

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

### EC2 IAM role and instance profile

```text
Role:             WeaveEC2BedrockRole
Instance profile: WeaveEC2BedrockProfile
```

Attached policies:

- `WeaveBedrockAccess`
- `AmazonSSMManagedInstanceCore`

The EC2 instance was launched with IMDSv2 required and response hop limit `2`.
The hop limit is important because the Bedrock client runs inside Docker.

### Security group

Name:

```text
weave-sg
```

Inbound rules:

| Type | Port | Source |
|---|---:|---|
| SSH | 22 | Current administrator public IP `/32` |
| HTTP | 80 | `0.0.0.0/0` |
| HTTPS | 443 | `0.0.0.0/0` |

If SSH times out after changing network, VPN, or location, update only the SSH
rule to **My IP** in the AWS Console. Keep ports 80 and 443 unchanged.

---

## 4. Automated Provisioning

The provisioning script is:

```text
scripts/deploy-ec2-bedrock.sh
```

It creates:

- Bedrock IAM policy
- EC2 role and instance profile
- Security group
- RSA key pair
- `t3.large` instance with encrypted 50 GB gp3
- 4 GB swap
- Elastic IP
- Docker and Docker Compose
- PostgreSQL, backend, and web containers
- Bedrock readiness and public health checks

On a Mac with valid AWS CLI credentials:

```bash
mkdir -p ~/weave-deploy

curl -fsSL \
  https://raw.githubusercontent.com/saurabhdsh/knowledgefabric/main/scripts/deploy-ec2-bedrock.sh \
  -o ~/weave-deploy/deploy-ec2-bedrock.sh

chmod +x ~/weave-deploy/deploy-ec2-bedrock.sh

aws sts get-caller-identity --region us-east-1

AWS_REGION=us-east-1 ~/weave-deploy/deploy-ec2-bedrock.sh
```

Type `DEPLOY` when prompted.

The local deployment state is stored only on the provisioning Mac:

```text
~/.weave/ec2/latest-deployment.env
~/.weave/ec2/keys/<generated-key-name>.pem
```

Protect these files. Never commit or share the PEM file.

---

## 5. Connecting to EC2

From the Mac that performed provisioning:

```bash
source ~/.weave/ec2/latest-deployment.env
ssh -i "$KEY_FILE" ec2-user@"$ELASTIC_IP"
```

If connection times out:

1. AWS Console -> EC2 -> Security Groups -> `weave-sg`.
2. Edit inbound rules.
3. Change the SSH rule source to **My IP**.
4. Save and retry.

The message below is harmless when using an SSH heredoc:

```text
Pseudo-terminal will not be allocated because stdin is not a terminal.
```

---

## 6. Weave Runtime Configuration

The EC2 `.env` lives at:

```text
/home/ec2-user/Knowledge-Fabric/.env
```

Important Bedrock settings:

```text
DEFAULT_LLM_PROVIDER=bedrock
BEDROCK_ENABLED=true
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
ENABLED_LLM_PROVIDERS=openai,bedrock
```

Do not add `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY`. The EC2 role supplies
temporary credentials.

The production stack is defined in:

- `docker-compose.ec2.yml`
- `docker-compose.domain.yml` (HTTPS/domain extension)
- `deploy/caddy/Caddyfile`

---

## 7. Docker Buildx Compatibility Fix

Amazon Linux installed a Docker environment without a sufficiently recent
Buildx plugin. Docker Compose reported:

```text
compose build requires buildx 0.17.0 or later
```

The fix is included in:

```text
scripts/ec2-setup.sh
```

It installs a compatible Docker Buildx release before building Weave. Commit:

```text
5d478fc Install compatible Docker Buildx on EC2
```

---

## 8. Browser Authentication Fix

After the first EC2 deployment, login succeeded but the Dashboard displayed:

```text
Load failed. Please check backend server and refresh.
```

The browser JWT was valid, but `InboundAPIKeyMiddleware` also demanded an
external `X-API-Key` for public-IP requests. The middleware now accepts a JWT
already validated by `JWTAuthMiddleware`; external integrations still require
an inbound API key.

Commit:

```text
efcb6c5 Allow authenticated UI sessions through API key middleware
```

To deploy backend updates:

```bash
source ~/.weave/ec2/latest-deployment.env

ssh -i "$KEY_FILE" ec2-user@"$ELASTIC_IP" <<'REMOTE'
cd ~/Knowledge-Fabric
git pull origin main
sudo docker compose -f docker-compose.ec2.yml up -d --build backend
sudo docker compose -f docker-compose.ec2.yml ps
REMOTE
```

---

## 9. GoDaddy DNS

DNS records:

| Type | Name | Value | TTL |
|---|---|---|---|
| A | `@` | `52.0.130.62` | 1 hour |
| CNAME | `www` | `cuweave.com.` | 1 hour |

The trailing dot in `cuweave.com.` is valid DNS notation.

Verify:

```bash
dig +short A cuweave.com
dig +short CNAME www.cuweave.com
```

Expected:

```text
52.0.130.62
cuweave.com.
```

Do not use GoDaddy URL forwarding. The DNS A record must continue pointing to
the Elastic IP.

---

## 10. Enabling Domain HTTPS

HTTPS support was added in commit:

```text
d47cb94 Add Caddy HTTPS support for EC2 domains
```

From the provisioning Mac:

```bash
source ~/.weave/ec2/latest-deployment.env

ssh -i "$KEY_FILE" ec2-user@"$ELASTIC_IP" <<'REMOTE'
cd ~/Knowledge-Fabric
git pull origin main
sudo bash scripts/enable-ec2-domain.sh cuweave.com
REMOTE
```

The domain setup script:

- Sets `REACT_APP_API_URL=https://cuweave.com`
- Sets CORS for `https://cuweave.com` and `https://www.cuweave.com`
- Moves the nginx web host binding to `127.0.0.1:8080`
- Starts Caddy on ports 80 and 443
- Obtains and automatically renews Let's Encrypt certificates
- Redirects HTTP to HTTPS
- Preserves all existing database and fabric volumes

Verify:

```text
https://cuweave.com
https://www.cuweave.com
https://cuweave.com/health
```

Certificate issuance normally takes 30-90 seconds after startup.

---

## 11. Health and Bedrock Validation

Public health:

```bash
curl -fsS https://cuweave.com/health
```

Expected components:

```text
api: healthy
database: healthy
chroma: healthy
job_worker: running
```

Bedrock readiness inside the backend container:

```bash
cd ~/Knowledge-Fabric

sudo docker compose \
  -f docker-compose.ec2.yml \
  -f docker-compose.domain.yml \
  exec -T backend \
  python -c "from app.core.config import settings; from app.services.llm.llm_router import llm_router; print('provider=', settings.DEFAULT_LLM_PROVIDER); print('bedrock_enabled=', settings.BEDROCK_ENABLED); print('bedrock_ready=', llm_router.is_provider_ready('bedrock'))"
```

Expected:

```text
provider= bedrock
bedrock_enabled= True
bedrock_ready= True
```

End-to-end UI test:

1. Login.
2. Create a small PDF or CSV fabric.
3. Confirm ontology discovery and graph build.
4. Open Test with LLM and select Bedrock.
5. Run a grounded question against the new fabric.

---

## 12. Day-2 Operations

### Check containers

```bash
cd ~/Knowledge-Fabric
sudo docker compose \
  -f docker-compose.ec2.yml \
  -f docker-compose.domain.yml \
  ps
```

### View logs

```bash
sudo docker compose \
  -f docker-compose.ec2.yml \
  -f docker-compose.domain.yml \
  logs -f backend
```

```bash
sudo docker compose \
  -f docker-compose.ec2.yml \
  -f docker-compose.domain.yml \
  logs -f caddy
```

### Pull and deploy application updates

```bash
cd ~/Knowledge-Fabric
git pull origin main
sudo docker compose \
  -f docker-compose.ec2.yml \
  -f docker-compose.domain.yml \
  up -d --build
```

### Restart without rebuilding

```bash
sudo docker compose \
  -f docker-compose.ec2.yml \
  -f docker-compose.domain.yml \
  restart
```

### Stop and start the stack

```bash
sudo docker compose \
  -f docker-compose.ec2.yml \
  -f docker-compose.domain.yml \
  stop
```

```bash
sudo docker compose \
  -f docker-compose.ec2.yml \
  -f docker-compose.domain.yml \
  start
```

Never run the command below unless intentionally deleting all persisted Weave
data:

```text
docker compose down -v
```

The `-v` option removes Postgres, Chroma, upload, ontology, model, and
certificate volumes.

---

## 13. Persistent Data

The EC2 deployment uses named Docker volumes:

| Volume purpose | Data |
|---|---|
| `postgres_data` | Users, fabrics, jobs, metadata |
| `backend_uploads` | Uploaded documents and codebases |
| `backend_chroma` | Vector indexes |
| `backend_models` | Trained model artifacts |
| `backend_data` | Fabric backup/runtime data |
| `backend_ontology` | Ontology projects and uploads |
| `caddy_data` | TLS certificates |
| `caddy_config` | Caddy runtime configuration |

Rebuilding or restarting containers does not delete these volumes.

Fabrics created on local Macs are not automatically copied to EC2. EC2 has its
own Postgres and vector volumes, so create/import fabrics in the EC2
environment.

---

## 14. Security Checklist

- Change the default `Saurabh / admin123` password immediately.
- Keep SSH port 22 restricted to a current administrator `/32` IP.
- Keep the PEM file under `~/.weave/ec2/keys` with permission `400`.
- Never store AWS user keys on EC2; use the instance role.
- Use only `https://cuweave.com` when sharing with demo users.
- Rotate `SECRET_KEY` and `POSTGRES_PASSWORD` before production use.
- Do not expose Postgres port 5432 publicly.
- Issue scoped inbound API keys only for external integrations.
- Revoke demo users after a customer demonstration.
- For a production rollout, add backups, CloudWatch alarms, WAF/ALB or another
  managed edge, corporate SSO, and stricter network controls.

---

## 15. Cost Controls

- Stop the EC2 instance when it will not be used for demos.
- Do not release the Elastic IP if the domain must keep the same address.
- EBS and the Elastic IP may still incur charges while EC2 is stopped.
- Monitor CPU, disk, and memory before upgrading from `t3.large`.
- Use `t3.xlarge` only when concurrent processing demonstrates a need.

---

## 16. Repository and Machine Locations

| Location | Purpose |
|---|---|
| Current development Mac | Source development and Git pushes |
| Bedrock Mac `~/knowledgefabric` | Local Bedrock-enabled Weave |
| Bedrock Mac `~/weave-deploy` | Downloaded provisioning script |
| Bedrock Mac `~/.weave/ec2` | EC2 state and private key |
| EC2 `/home/ec2-user/Knowledge-Fabric` | Deployed application clone |

Git pushes are already performed from the development Mac. On the Bedrock Mac
or EC2, normally run `git pull origin main`; do not push deployment state or
`.env`.

---

## 17. Relevant Deployment Commits

| Commit | Purpose |
|---|---|
| `44d62c9` | Sanitize CSV NaN/Infinity values that broke fabric listing |
| `a25aaad` | One-command EC2 + Bedrock provisioning |
| `5d478fc` | Install compatible Docker Buildx on EC2 |
| `efcb6c5` | Allow authenticated UI JWT through API-key middleware |
| `d47cb94` | Add Caddy/Let's Encrypt HTTPS domain support |

---

## 18. Current Status Checklist

- [x] Bedrock IAM policy and EC2 role created
- [x] EC2 `t3.large`, 50 GB gp3, and 4 GB swap created
- [x] Elastic IP `52.0.130.62` associated
- [x] Weave Docker services deployed
- [x] HTTP API/frontend health verified
- [x] GoDaddy A and CNAME records propagated
- [x] Security-group HTTPS port 443 added
- [ ] Update SSH allowlist if the administrator IP changed
- [ ] Run `scripts/enable-ec2-domain.sh cuweave.com`
- [ ] Verify Let's Encrypt certificate and HTTPS health
- [ ] Change the default administrator password
- [ ] Validate Bedrock through Test with LLM
- [ ] Create first EC2-hosted fabric and validate persistence
