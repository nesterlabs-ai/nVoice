#!/bin/bash
# Test LightRAG API Authentication

API_KEY="805c5c51f72690e3d60a94feba3e9958bef824f28332f25f3f5638ef6f6d642f"
API_URL="http://16.170.172.18"

echo "Testing LightRAG API..."
echo "API URL: $API_URL"
echo "API Key: ${API_KEY:0:20}...${API_KEY: -10}"
echo ""

# Test query
echo "Sending test query: 'What is AI?'"
curl -X POST "$API_URL/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"query":"What is AI?","mode":"local"}' \
  --max-time 20 \
  --silent \
  --show-error

echo ""
echo ""
echo "Testing health endpoint..."
curl -X GET "$API_URL/health" \
  -H "ngrok-skip-browser-warning: true" \
  --max-time 10 \
  --silent \
  --show-error

echo ""
