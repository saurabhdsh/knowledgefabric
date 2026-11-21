# Weave on the Azure VM at cuweave.com

The app runs on `rapid-build-dev-server` (`20.127.186.132`) in its own Compose project. Caddy on that VM serves `https://cuweave.com` and `https://www.cuweave.com`. Ports 3000, 5173, and 8000 stay with SEAL and SciNova. Postgres is not published.

Chat uses Azure OpenAI at `https://exxondemofdr.cognitiveservices.azure.com/openai/v1`, deployment `gpt-5-mini`. The key is pasted into `.env` on the VM and is not committed.

The VM already runs other stacks on 8 GiB. If Weave is killed by the kernel, resize the VM to `Standard_D4s_v3`.

## 1. Open ports 80 and 443

```bash
az login
az account set --subscription "eb2757c6-7b0f-409c-89a9-3d949470d9d0"
az network nsg rule create \
  --resource-group "RAPID-BUILD-DEV-SERVER_GROUP" \
  --nsg-name "rapid-build-dev-server-nsg" \
  --name "Weave-HTTP-80" \
  --priority 340 \
  --access Allow \
  --protocol Tcp \
  --direction Inbound \
  --source-address-prefixes "*" \
  --destination-port-ranges 80
az network nsg rule create \
  --resource-group "RAPID-BUILD-DEV-SERVER_GROUP" \
  --nsg-name "rapid-build-dev-server-nsg" \
  --name "Weave-HTTPS-443" \
  --priority 350 \
  --access Allow \
  --protocol Tcp \
  --direction Inbound \
  --source-address-prefixes "*" \
  --destination-port-ranges 443
```

Skip a rule that already exists. Nothing else on the VM should be listening on 80 or 443.

## 2. Point GoDaddy at the VM

In GoDaddy, open the `cuweave.com` DNS records and replace the EC2 address `52.0.130.62`.

| Type | Name | Value | TTL |
|------|------|--------|-----|
| A | `@` | `20.127.186.132` | 600 seconds |
| A | `www` | `20.127.186.132` | 600 seconds |

Delete any other A or CNAME record for `@` or `www` that still points at the EC2 host. Do not add a forwarding rule. The VM answers HTTP and HTTPS itself.

Wait until both names resolve to the VM:

```bash
dig +short A cuweave.com
dig +short A www.cuweave.com
```

Both should print `20.127.186.132` before the first Caddy start. Let's Encrypt uses that path on port 80.

## 3. Start Weave on the VM

```bash
ssh azureuser@20.127.186.132
git clone https://github.com/saurabhdsh/knowledgefabric.git weave
cd weave
cp env.azure.example .env
# Paste the Azure OpenAI key as OPENAI_API_KEY. Do not commit .env.
sudo docker compose -f docker-compose.azure.yml up -d --build
```

After any `.env` change, recreate the containers:

```bash
sudo docker compose -f docker-compose.azure.yml up -d
```

A frontend URL change also needs a rebuild:

```bash
sudo docker compose -f docker-compose.azure.yml up -d --build web
```

Check the chat key before relying on the UI. Do not print the key:

```bash
KEY="$(grep '^OPENAI_API_KEY=' .env | cut -d= -f2-)"
curl -sS "https://exxondemofdr.cognitiveservices.azure.com/openai/v1/chat/completions" \
  -H "Authorization: Bearer ${KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5-mini","messages":[{"role":"user","content":"Reply with exactly: PONG"}]}'
```

A working call returns `PONG`. Then open `https://cuweave.com`.
