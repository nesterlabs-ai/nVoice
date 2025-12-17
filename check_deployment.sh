#!/bin/bash
# Script to verify deployment and check configuration

echo "=== Deployment Verification ==="
echo ""

# Get SSH key path (try both locations)
if [ -f "LightsailDefaultKey-ap-south-1.pem" ]; then
    SSH_KEY="LightsailDefaultKey-ap-south-1.pem"
elif [ -f "~/.ssh/LightsailDefaultKey-ap-south-1.pem" ]; then
    SSH_KEY="~/.ssh/LightsailDefaultKey-ap-south-1.pem"
else
    echo "Error: SSH key not found"
    exit 1
fi

SERVER="ubuntu@3.6.64.48"

echo "1. Checking GitHub Actions deployment status..."
echo "   Visit: https://github.com/akkupratap323/NesterVoiceAI/actions"
echo ""

echo "2. Checking Docker container status..."
ssh -i "$SSH_KEY" "$SERVER" "cd nester-ai-bot && docker ps --format 'table {{.Names}}\t{{.Status}}'" 2>/dev/null || echo "   Unable to connect via SSH"
echo ""

echo "3. Checking backend container logs (last 30 lines)..."
ssh -i "$SSH_KEY" "$SERVER" "cd nester-ai-bot && docker logs nester-backend --tail 30" 2>/dev/null || echo "   Unable to fetch logs"
echo ""

echo "4. Checking if RAG mode is 'naive' in container..."
ssh -i "$SSH_KEY" "$SERVER" "cd nester-ai-bot && docker exec nester-backend cat /app/app/config/config.yaml | grep -A 3 'rag:'" 2>/dev/null || echo "   Unable to check config"
echo ""

echo "5. Testing backend health endpoint..."
curl -s https://3.6.64.48.nip.io/health | python3 -m json.tool 2>/dev/null || curl -s https://3.6.64.48.nip.io/health
echo ""

echo "6. Testing RAG query with naive mode..."
API_KEY="805c5c51f72690e3d60a94feba3e9958bef824f28332f25f3f5638ef6f6d642f"
curl -s -X POST "http://16.170.172.18/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d '{"query":"What is Nesterlabs?","mode":"naive"}' | python3 -c "
import sys, json
data = json.load(sys.stdin)
response = data.get('response', '')
print('Response preview:', response[:200] + '...' if len(response) > 200 else response)
" 2>/dev/null || echo "Unable to test RAG"

echo ""
echo "=== Verification Complete ==="
