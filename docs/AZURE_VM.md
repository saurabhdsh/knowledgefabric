# Weave on the Azure VM, with cuweave.com still on EC2

The app runs on `rapid-build-dev-server` (`20.127.186.132`) in its own Compose project. Ports 3000, 5173, and 8000 stay with SEAL and SciNova. Weave publishes **8080** only. Postgres is not published.

`cuweave.com` keeps its DNS and certificate on the EC2 host (`52.0.130.62`). Caddy on that host forwards the site to `http://20.127.186.132:8080`. Chat uses Azure OpenAI at `https://exxondemofdr.cognitiveservices.azure.com/openai/v1`, deployment `gpt-5-mini`. The key is pasted into `.env` on the VM and is not committed.

The VM already runs other stacks on 8 GiB. If Weave is killed by the kernel, resize the VM to `Standard_D4s_v3`.

## 1. Open port 8080

```bash
az login
az account set --subscription "eb2757c6-7b0f-409c-89a9-3d949470d9d0"
az network nsg rule create \
  --resource-group "RAPID-BUILD-DEV-SERVER_GROUP" \
  --nsg-name "rapid-build-dev-server-nsg" \
  --name "Weave-UI-8080" \
  --priority 340 \
  --access Allow \
  --protocol Tcp \
  --direction Inbound \
  --source-address-prefixes "*" \
  --destination-port-ranges 8080
```

## 2. Start Weave on the VM

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

Check the chat key before relying on the UI. Do not print the key:

```bash
KEY="$(grep '^OPENAI_API_KEY=' .env | cut -d= -f2-)"
curl -sS "https://exxondemofdr.cognitiveservices.azure.com/openai/v1/chat/completions" \
  -H "Authorization: Bearer ${KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5-mini","messages":[{"role":"user","content":"Reply with exactly: PONG"}]}'
```

A working call returns `PONG`. Direct UI: `http://20.127.186.132:8080`.

## 3. Point cuweave.com at the VM

On the EC2 host, in the existing Weave checkout:

```bash
sudo bash scripts/point-cuweave-at-azure.sh
```

That sets `WEAVE_UPSTREAM=20.127.186.132:8080` and recreates Caddy. `https://cuweave.com` and `https://www.cuweave.com` then reach the Azure stack. To send the domain back to the EC2 containers, set `WEAVE_UPSTREAM=web:80` and run the same compose command.
