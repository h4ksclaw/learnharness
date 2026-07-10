#!/usr/bin/env bash
set -euo pipefail

# LearnHarness — One-command Deploy on Oracle Cloud (or any Linux VM)
# Tested on: Oracle Cloud Ampere A1 (ARM), Ubuntu 22.04
# Also works on: any Ubuntu/Debian VM with Docker support

echo "╔══════════════════════════════════════════════════╗"
echo "║     LearnHarness — Demo Deployment Setup         ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ No .env file found!"
    echo "   cp deploy/.env.example .env"
    echo "   Then edit it with your Groq API key"
    exit 1
fi

# Source env
set -a
source .env
set +a

if [ -z "${LLM_API_KEY:-}" ] || [ "$LLM_API_KEY" = "your-groq-api-key-here" ]; then
    echo "❌ LLM_API_KEY not set in .env"
    echo "   Get a free key at: https://console.groq.com/keys"
    exit 1
fi

echo "✅ .env loaded"
echo "   LLM: ${LLM_MODEL} via ${LLM_BASE_URL}"
echo ""

# Build and start everything
echo "🔨 Building and starting containers..."
docker compose -f compose.yaml -f deploy/compose.demo.yaml up -d --build

echo ""
echo "⏳ Waiting for services to start..."
sleep 10

# Health check
echo "🏥 Health checks..."
max_retries=30
for i in $(seq 1 $max_retries); do
    if curl -sf http://localhost:${API_PORT:-8000}/v1/agents > /dev/null 2>&1; then
        echo "   ✅ API is up"
        break
    fi
    echo "   ...waiting ($i/$max_retries)"
    sleep 2
done

if curl -sf http://localhost:${WEB_PORT:-3000} > /dev/null 2>&1; then
    echo "   ✅ Web UI is up"
else
    echo "   ⚠️  Web UI still starting (may need 30s for first build)"
fi

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  🎉 Deploy complete!                             ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║                                                  ║"
echo "║  Web UI:  http://$(hostname -I | awk '{print $1}'):${WEB_PORT:-3000}  ║"
echo "║  API:     http://$(hostname -I | awk '{print $1}'):${API_PORT:-8000}  ║"
echo "║  Docs:    http://$(hostname -I | awk '{print $1}'):${API_PORT:-8000}/docs  ║"
echo "║                                                  ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Logs:     docker compose logs -f"
echo "Stop:     docker compose down"
echo "Restart:  docker compose up -d"
