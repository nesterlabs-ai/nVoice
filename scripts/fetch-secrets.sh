#!/bin/bash
# Fetch secrets from AWS Secrets Manager and create .env file
# Run this on the Lightsail server during deployment

ENV_FILE="${1:-/home/ec2-user/nester-bot/.env}"
REGION="ap-south-1"
SECRET_NAME="nester/voice-bot/secrets"

echo "🔐 Fetching secrets from AWS Secrets Manager..."

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found"
    exit 1
fi

echo "📥 Downloading secrets from: $SECRET_NAME..."

# Fetch secret from Secrets Manager
SECRET_JSON=$(aws secretsmanager get-secret-value \
    --secret-id "$SECRET_NAME" \
    --region "$REGION" \
    --query SecretString \
    --output text 2>/dev/null)

if [ -z "$SECRET_JSON" ]; then
    echo "❌ Failed to fetch secret from Secrets Manager"
    echo "   Falling back to Parameter Store..."
    
    # Fallback to Parameter Store for backward compatibility
    DEEPGRAM_API_KEY=$(aws ssm get-parameter --name "/nester/DEEPGRAM_API_KEY" --with-decryption --region $REGION --query "Parameter.Value" --output text 2>/dev/null || echo "")
    OPENAI_API_KEY=$(aws ssm get-parameter --name "/nester/OPENAI_API_KEY" --with-decryption --region $REGION --query "Parameter.Value" --output text 2>/dev/null || echo "")
    GOOGLE_API_KEY=$(aws ssm get-parameter --name "/nester/GOOGLE_API_KEY" --with-decryption --region $REGION --query "Parameter.Value" --output text 2>/dev/null || echo "")
    ELEVENLABS_API_KEY=$(aws ssm get-parameter --name "/nester/ELEVENLABS_API_KEY" --with-decryption --region $REGION --query "Parameter.Value" --output text 2>/dev/null || echo "")
    ELEVENLABS_VOICE_ID=$(aws ssm get-parameter --name "/nester/ELEVENLABS_VOICE_ID" --with-decryption --region $REGION --query "Parameter.Value" --output text 2>/dev/null || echo "")
    PINECONE_API_KEY=$(aws ssm get-parameter --name "/nester/PINECONE_API_KEY" --with-decryption --region $REGION --query "Parameter.Value" --output text 2>/dev/null || echo "")
    PINECONE_INDEX=$(aws ssm get-parameter --name "/nester/PINECONE_INDEX" --with-decryption --region $REGION --query "Parameter.Value" --output text 2>/dev/null || echo "")
    PUBLIC_URL=$(aws ssm get-parameter --name "/nester/PUBLIC_URL" --with-decryption --region $REGION --query "Parameter.Value" --output text 2>/dev/null || echo "")
    LIGHTRAG_API_KEY=$(aws ssm get-parameter --name "/nester/LIGHTRAG_API_KEY" --with-decryption --region $REGION --query "Parameter.Value" --output text 2>/dev/null || echo "")
    
    cat > "$ENV_FILE" << EOF
# Auto-generated from AWS Parameter Store (fallback)
# Do not edit manually - changes will be overwritten on next deploy
# Last updated: $(date)

# Required API Keys
DEEPGRAM_API_KEY=$DEEPGRAM_API_KEY
OPENAI_API_KEY=$OPENAI_API_KEY
GOOGLE_API_KEY=$GOOGLE_API_KEY
ELEVENLABS_API_KEY=$ELEVENLABS_API_KEY
ELEVENLABS_VOICE_ID=$ELEVENLABS_VOICE_ID
LIGHTRAG_API_KEY=$LIGHTRAG_API_KEY

# Pinecone RAG Configuration
PINECONE_API_KEY=$PINECONE_API_KEY
PINECONE_INDEX=$PINECONE_INDEX

# Server Configuration
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=7860
WEBSOCKET_HOST=0.0.0.0
WEBSOCKET_PORT=8765
WEBSOCKET_SERVER=fast_api
PUBLIC_URL=$PUBLIC_URL

# Session Settings
SESSION_TIMEOUT=180
LOG_LEVEL=INFO
DOMAIN=3.6.64.48.nip.io
EOF
else
    echo "✅ Secret fetched from Secrets Manager"
    echo "📝 Creating $ENV_FILE..."
    
    # Convert JSON to .env format using Python
    python3 << PYTHON_SCRIPT > "$ENV_FILE"
import json
import sys
from datetime import datetime

try:
    secret_data = json.loads('''$SECRET_JSON''')
    
    # Write header
    print("# Auto-generated from AWS Secrets Manager")
    print("# Do not edit manually - changes will be overwritten on next deploy")
    print(f"# Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("")
    
    # Write all key-value pairs
    for key, value in sorted(secret_data.items()):
        if value:  # Only write non-empty values
            # Escape special characters in value
            value = str(value).replace('\\', '\\\\').replace('$', '\\$').replace('`', '\\`')
            print(f"{key}={value}")
    
    sys.exit(0)
except Exception as e:
    print(f"# Error parsing secret: {e}", file=sys.stderr)
    sys.exit(1)
PYTHON_SCRIPT
    
    if [ $? -ne 0 ]; then
        echo "❌ Failed to parse secret JSON"
        exit 1
    fi
fi

# Secure the file
chmod 600 "$ENV_FILE"

echo "✅ Secrets loaded"
echo "📁 File: $ENV_FILE"
echo "🔒 Permissions: 600 (owner read/write only)"
echo ""
echo "📋 Loaded secrets:"
grep -E '^[A-Z_]+=' "$ENV_FILE" | cut -d= -f1 | sed 's/^/   - /'

