#!/bin/bash
# Test LightRAG queries for Nester Labs information

API_KEY="805c5c51f72690e3d60a94feba3e9958bef824f28332f25f3f5638ef6f6d642f"
API_URL="http://16.170.172.18"

echo "Testing RAG queries for Nester Labs..."
echo ""

# Test 1: Direct query about Nester Labs
echo "1. Query: 'What is Nester Labs?'"
curl -X POST "$API_URL/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"query":"What is Nester Labs?","mode":"local"}' \
  --silent | python3 -m json.tool 2>/dev/null || curl -X POST "$API_URL/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"query":"What is Nester Labs?","mode":"local"}' \
  --silent

echo -e "\n\n"

# Test 2: Query about company
echo "2. Query: 'Tell me about the company'"
curl -X POST "$API_URL/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"query":"Tell me about the company","mode":"local"}' \
  --silent | python3 -m json.tool 2>/dev/null || curl -X POST "$API_URL/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"query":"Tell me about the company","mode":"local"}' \
  --silent

echo -e "\n\n"

# Test 3: List documents
echo "3. Checking document status..."
curl -X GET "$API_URL/documents" \
  -H "X-API-Key: $API_KEY" \
  --silent | python3 -m json.tool 2>/dev/null || curl -X GET "$API_URL/documents" \
  -H "X-API-Key: $API_KEY" \
  --silent

echo ""
