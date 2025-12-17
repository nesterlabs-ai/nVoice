#!/bin/bash
set -e

API_KEY="805c5c51f72690e3d60a94feba3e9958bef824f28332f25f3f5638ef6f6d642f"
API_URL="http://16.170.172.18"

echo "Testing NAIVE mode for Nesterlabs..."
curl -X POST "${API_URL}/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d '{"query":"Tell me about Nesterlabs","mode":"naive"}' \
  --silent --show-error

echo -e "\n\n"
echo "Testing HYBRID mode for Nesterlabs..."
curl -X POST "${API_URL}/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d '{"query":"What is Nesterlabs?","mode":"hybrid"}' \
  --silent --show-error
