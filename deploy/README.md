# Deploy Guide

## Option 1: Oracle Cloud Always Free (recommended — full stack, free forever)

Oracle Cloud gives you a **free ARM VM with 24GB RAM and 4 CPU cores** — enough to run the entire Docker stack including Postgres and the web UI.

### Step 1: Get the VM

1. Sign up at [oracle.com/cloud/free](https://www.oracle.com/cloud/free/)
2. Create a compute instance:
   - Shape: **VM.Standard.A1.Flex** (Ampere ARM, free tier)
   - Image: **Ubuntu 22.04** (or Canonical Ubuntu)
   - Allocate: 4 OCPUs, 24GB RAM (all free tier)
   - SSH keys: add your public key
3. Open ports in security list: **3000** (web) and **8000** (API)
4. SSH in: `ssh ubuntu@<your-vm-ip>`

### Step 2: Install Docker

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker $USER
newgrp docker
```

### Step 3: Deploy

```bash
git clone https://github.com/h4ksclaw/learnharness.git
cd learnharness

# Get free Groq API key at https://console.groq.com/keys
cp deploy/.env.example .env
nano .env  # paste your Groq key

# One command:
bash deploy/setup.sh
```

### Step 4: Access

- **Web UI**: `http://<vm-ip>:3000`
- **API docs**: `http://<vm-ip>:8000/docs`

Done. The whole stack runs as Docker containers — Postgres, API, worker, web UI. No Ollama needed (using Groq's free LLM API instead).

---

## What's running

| Container | Purpose | Port |
|-----------|---------|------|
| db | PostgreSQL 16 + pgvector | 5432 (internal) |
| api | FastAPI backend | 8000 |
| worker | Background heartbeat scheduler | - |
| web | Next.js frontend | 3000 |

Ollama is excluded from the demo stack — we use [Groq](https://groq.com) (free, fast LLM API) instead.

---

## LLM Options (all free)

| Provider | Model | Base URL | Notes |
|----------|-------|----------|-------|
| **Groq** | llama-3.3-70b-versatile | `https://api.groq.com/openai/v1` | Fastest, recommended |
| Google | gemini-1.5-flash | `https://generativelanguage.googleapis.com/v1beta/openai/` | Generous free tier |
| OpenRouter | Various | `https://openrouter.ai/api/v1` | Free + paid models |

Any OpenAI-compatible API works — just change `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` in `.env`.

---

## Other Free Hosts

### Fly.io
Works but tight on RAM. Free tier = 3 shared VMs × 256MB. Enough for API + web but Postgres needs a dedicated VM (free 3GB DB included).

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# From repo root:
fly launch --no-deploy
fly vol create lh_data -s 1
fly deploy
```

### Render
Split services: web service (free, sleeps after 15min) + Postgres (free 90 days) + background worker. Cold starts make demos feel slow.

---

## Troubleshooting

### ARM compatibility
All images used are multi-arch (amd64 + arm64): Python, Postgres, Node. No changes needed.

### Groq rate limits
Free tier: ~30 requests/min, ~14k tokens/min. Fine for demos. If you hit limits, the API will return 429 — the app handles this gracefully.

### Database persistence
The Postgres data volume persists across restarts. To wipe: `docker compose down -v`.

### Updating
```bash
git pull
docker compose -f compose.yaml -f deploy/compose.demo.yaml up -d --build
```
