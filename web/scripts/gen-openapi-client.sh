#!/usr/bin/env bash
set -euo pipefail

# Generate OpenAPI client from the running API (or from exported schema)
# Usage: ./scripts/gen-openapi-client.sh [api-url]

API_URL="${1:-http://localhost:8000}"
OUTPUT_DIR="src/lib/api-client"
SPEC_FILE="/tmp/learnharness-openapi.json"

# Check if java is available (openapi-generator-cli needs it)
if ! command -v java &>/dev/null; then
    echo "⚠️  java not found — skipping client generation"
    echo "   Install JDK or run: npm run gen-client (requires Java)"
    exit 0
fi

echo "📡 Fetching OpenAPI spec from $API_URL/openapi.json ..."
if curl -sf "$API_URL/openapi.json" -o "$SPEC_FILE"; then
    echo "✅ Got spec from running API"
else
    echo "⚠️  API not running at $API_URL — skipping client generation"
    echo "   Start the backend first: docker compose up -d api"
    exit 0
fi

echo "🔧 Generating TypeScript client..."
npx @openapitools/openapi-generator-cli generate \
    -i "$SPEC_FILE" \
    -g typescript-fetch \
    -o "$OUTPUT_DIR" \
    --additional-properties=supportsES6=true,typescriptThreePlus=true

echo "✅ OpenAPI client generated at $OUTPUT_DIR"
