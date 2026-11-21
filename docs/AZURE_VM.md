# Weave on the Azure VM at cuweave.com

The app runs on `rapid-build-dev-server` (`20.127.186.132`) in its own Compose project. SciNova already uses ports 80 and 443, so Weave is at `http://cuweave.com:8080`. Ports 3000, 5173, and 8000 stay with SEAL and SciNova. Postgres is not published.

Chat uses Azure OpenAI at `https://exxondemofdr.cognitiveservices.azure.com/openai/v1`, deployment `gpt-5-mini`. The key is pasted into `.env` on the VM and is not committed.

The VM already runs other stacks on 8 GiB. If Weave is killed by the kernel, resize the VM to `Standard_D4s_v3`.

## 1. Open port 8080

In the portal, on `rapid-build-dev-server-nsg`, choose **Create port rule**. Leave the SciNova HTTPS rule on 443 as it is.

| Field | Value |
|-------|--------|
| Source | Any |
| Source port ranges | * |
| Destination | Any |
| Service | Custom |
| Destination port ranges | 8080 |
| Protocol | TCP |
| Action | Allow |
| Priority | 350 |
| Name | Weave-HTTP-8080 |

Port 80 in the current list only allows traffic from inside the virtual network. That rule does not publish Weave.

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

Both should print `20.127.186.132`. The `www` CNAME to `cuweave.com` is already the right record.

## 3. Run the setup on the VM

```bash
ssh azureuser@20.127.186.132
git clone https://github.com/saurabhdsh/knowledgefabric.git weave
cd weave
sudo bash scripts/azure-setup.sh
```

The script writes `.env`, generates the app secret and database password, and asks you to paste the Azure OpenAI endpoint and key. Press Enter on the endpoint to keep `https://exxondemofdr.cognitiveservices.azure.com/openai/v1`. It does not print the key. Run the same command again after a later `git pull`.

Then open `http://cuweave.com:8080`. The first login is **Saurabh** / **admin123**. Change that password after signing in.
