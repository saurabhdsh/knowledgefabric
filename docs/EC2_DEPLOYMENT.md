# Weave on AWS EC2 (simple public URL)

Deploy Weave on **one EC2 instance** and open it at `http://<public-ip>`.

---

## What you create in AWS

| Item | Setting |
|------|---------|
| **EC2 instance** | Amazon Linux 2023 or Ubuntu 22.04 |
| **Instance type** | `t3.large` minimum (8 GB RAM recommended: `t3.xlarge`) |
| **Storage** | 50 GB+ gp3 |
| **Security group** | Inbound: **22** (SSH), **80** (HTTP) from your IP or `0.0.0.0/0` |
| **IAM role** | Attach role with **Bedrock invoke** permissions (see below) |
| **Elastic IP** (recommended) | So the URL does not change after reboot |

---

## Step 1 — Launch EC2

1. AWS Console → **EC2** → **Launch instance**
2. Name: `weave-server`
3. AMI: **Amazon Linux 2023** (or Ubuntu 22.04)
4. Type: **t3.large** or larger
5. Key pair: create/download a `.pem` file
6. Security group: allow **SSH (22)** and **HTTP (80)**
7. **Advanced details → IAM instance profile**: attach a role with Bedrock access
8. Launch

### IAM policy for Bedrock (attach to EC2 role)

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

Also enable your model in **Bedrock → Model access** (e.g. Claude 3.5 Sonnet).

### Elastic IP (optional but recommended)

1. EC2 → **Elastic IPs** → Allocate
2. Associate with your `weave-server` instance

---

## Step 2 — Copy code to EC2

From your laptop:

```bash
# Replace with your key and EC2 public IP
export EC2_IP=3.110.xxx.xxx
export KEY=~/Downloads/weave-key.pem

# Option A: rsync the project
rsync -avz --exclude node_modules --exclude .venv --exclude backend/chroma_db \
  -e "ssh -i $KEY" Knowledge-Fabric/ ec2-user@$EC2_IP:~/Knowledge-Fabric/

# Option B: git clone on the server (if repo is on GitHub)
ssh -i $KEY ec2-user@$EC2_IP
git clone <your-repo-url> Knowledge-Fabric
```

**Note:** Amazon Linux user is `ec2-user`; Ubuntu uses `ubuntu`.

---

## Step 3 — Run setup on EC2

SSH into the instance:

```bash
ssh -i ~/Downloads/weave-key.pem ec2-user@<EC2_PUBLIC_IP>
cd ~/Knowledge-Fabric
sudo bash scripts/ec2-setup.sh
```

The script will:

1. Install Docker + Compose
2. Detect the public IP
3. Create `.env` with Bedrock + CORS settings
4. Build and start containers (`postgres`, `backend`, `nginx` on port **80**)

First build takes **10–15 minutes** (downloads models/deps).

> **Codebase fabrics:** the backend image needs `git` + OpenSSH (included in `backend/Dockerfile`). Leave enough disk for clones under `uploads/codebase/`. See [CODEBASE_FABRIC.md](./CODEBASE_FABRIC.md).

---

## Step 4 — Open Weave

```text
http://<EC2_PUBLIC_IP>
```

- Login: **Saurabh** / **admin123**
- API health: `http://<EC2_PUBLIC_IP>/health`
- API docs: `http://<EC2_PUBLIC_IP>/docs`

---

## Manual start (without setup script)

```bash
cd Knowledge-Fabric
cp env.ec2.example .env
# Edit .env: set REACT_APP_API_URL and KF_CORS_ORIGINS to http://<your-ip>
docker compose -f docker-compose.ec2.yml up -d --build
```

---

## Useful commands on EC2

```bash
docker compose -f docker-compose.ec2.yml ps
docker compose -f docker-compose.ec2.yml logs -f backend
docker compose -f docker-compose.ec2.yml restart
docker compose -f docker-compose.ec2.yml down
```

After code changes:

```bash
docker compose -f docker-compose.ec2.yml up -d --build
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Cannot open URL | Security group must allow **port 80** |
| Login works but API fails | `REACT_APP_API_URL` in `.env` must match public URL; rebuild: `docker compose -f docker-compose.ec2.yml up -d --build web` |
| Bedrock errors | EC2 IAM role + model enabled in Bedrock console |
| Out of memory | Use `t3.xlarge` (16 GB) |
| IP changed after stop/start | Attach an **Elastic IP** and update `.env`, then rebuild web |

---

## Security notes (POC vs production)

**POC (current guide):** HTTP on port 80, default password.

**Before production:**

- Change Saurabh password after first login
- Rotate `SECRET_KEY` and `POSTGRES_PASSWORD` in `.env`
- Restrict SSH (port 22) to your office IP
- Add HTTPS (ACM + ALB, or Caddy/Let’s Encrypt on EC2)
- Restrict port 80 to VPN / corporate network if internal-only
