#!/bin/bash
# Fetch secrets from AWS Parameter Store and create .env file
# Run this on the Lightsail server during deployment

set -e

ENV_FILE="${1:-/home/ec2-user/nester-bot/.env}"
REGION="ap-south-1"

echo "🔐 Fetching secrets from AWS Parameter Store..."

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found"
    exit 1
fi

# Function to get a parameter
get_param() {
    local name=$1
    aws ssm get-parameter \
        --name "/nester/$name" \
        --with-decryption \
        --region $REGION \
        --query "Parameter.Value" \
        --output text 2>/dev/null || echo ""
}

echo "📥 Downloading secrets..."

# Fetch all parameters
DEEPGRAM_API_KEY=$(get_param "DEEPGRAM_API_KEY")
OPENAI_API_KEY=$(get_param "OPENAI_API_KEY")
GOOGLE_API_KEY=$(get_param "GOOGLE_API_KEY")
ELEVENLABS_API_KEY=$(get_param "ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID=$(get_param "ELEVENLABS_VOICE_ID")
PINECONE_API_KEY=$(get_param "PINECONE_API_KEY")
PINECONE_INDEX=$(get_param "PINECONE_INDEX")
PUBLIC_URL=$(get_param "PUBLIC_URL")

# Create .env file
echo "📝 Creating $ENV_FILE..."

cat > "$ENV_FILE" << EOF
# Auto-generated from AWS Parameter Store
# Do not edit manually - changes will be overwritten on next deploy
# Last updated: $(date)

# Required API Keys
DEEPGRAM_API_KEY=$DEEPGRAM_API_KEY
OPENAI_API_KEY=$OPENAI_API_KEY
GOOGLE_API_KEY=$GOOGLE_API_KEY
ELEVENLABS_API_KEY=$ELEVENLABS_API_KEY
ELEVENLABS_VOICE_ID=$ELEVENLABS_VOICE_ID

# Pinecone RAG Configuration
PINECONE_API_KEY=$PINECONE_API_KEY
PINECONE_INDEX=$PINECONE_INDEX

# Server Configuration
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=7860
WEBSOCKET_HOST=0.0.0.0
WEBSOCKET_PORT=8765
WEBSOCKET_SERVER=websocket_server
PUBLIC_URL=$PUBLIC_URL

# Session Settings
SESSION_TIMEOUT=180
LOG_LEVEL=INFO
EOF

# Secure the file
chmod 600 "$ENV_FILE"

echo "✅ Secrets loaded from AWS Parameter Store"
echo "📁 File: $ENV_FILE"
echo "🔒 Permissions: 600 (owner read/write only)"

