#!/bin/bash
# Lightsail deployment script
# This script handles git sync, secret fetching, and container deployment
# Designed to be idempotent and fail-fast

set -euo pipefail

# Configuration
DEPLOY_DIR="${DEPLOY_DIR:-/home/ec2-user/nester-bot}"
GIT_REPO="${GIT_REPO:-https://github.com/nesterlabs-ai/NesterAIBot.git}"
GIT_BRANCH="${GIT_BRANCH:-main}"
AWS_REGION="${AWS_REGION:-ap-south-1}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
GHCR_TOKEN="${GHCR_TOKEN:-}"
GHCR_USER="${GHCR_USER:-}"
PUBLIC_URL="${PUBLIC_URL:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Change to deployment directory
cd "$DEPLOY_DIR" || {
    log_error "Deployment directory not found: $DEPLOY_DIR"
    exit 1
}

log_info "Starting deployment in: $DEPLOY_DIR"

# Step 1: Git synchronization
log_info "Step 1: Synchronizing code repository..."
if [ ! -d .git ]; then
    log_warn ".git directory not found, initializing repository..."
    git init
    git remote add origin "$GIT_REPO" || git remote set-url origin "$GIT_REPO"
fi

# Ensure we're on the correct remote
git remote set-url origin "$GIT_REPO"

# Fetch and reset to ensure clean state (deployment target only)
log_info "Fetching latest changes from $GIT_BRANCH..."
git fetch origin "$GIT_BRANCH" || {
    log_error "Failed to fetch from origin"
    exit 1
}

log_info "Resetting to origin/$GIT_BRANCH (deployment target - no local changes preserved)..."
git reset --hard "origin/$GIT_BRANCH" || {
    log_error "Failed to reset to origin/$GIT_BRANCH"
    exit 1
}

log_info "Current commit: $(git log -1 --oneline)"

# Step 2: Fetch secrets
log_info "Step 2: Fetching secrets from AWS Secrets Manager..."
if [ -f scripts/fetch-secrets.sh ]; then
    bash scripts/fetch-secrets.sh .env || {
        log_error "Failed to fetch secrets"
        exit 1
    }
else
    log_error "fetch-secrets.sh not found in repository"
    exit 1
fi

# Step 3: Docker login
log_info "Step 3: Authenticating with GitHub Container Registry..."
if [ -z "$GHCR_TOKEN" ] || [ -z "$GHCR_USER" ]; then
    log_error "GHCR_TOKEN or GHCR_USER not set"
    exit 1
fi

echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin || {
    log_error "Failed to login to GHCR"
    exit 1
}

# Step 4: Pull latest images
log_info "Step 4: Pulling latest Docker images..."
if [ ! -f docker-compose.https.yml ]; then
    log_error "docker-compose.https.yml not found"
    exit 1
fi

# Verify compose file uses image references (not build:)
if grep -q "build:" docker-compose.https.yml; then
    log_error "docker-compose.https.yml contains 'build:' sections. Use 'image:' references instead."
    exit 1
fi

# Export IMAGE_TAG for docker-compose to use
export IMAGE_TAG

docker-compose -f docker-compose.https.yml pull || {
    log_error "Failed to pull Docker images"
    exit 1
}

# Step 5: Deploy containers
log_info "Step 5: Deploying containers..."
docker-compose -f docker-compose.https.yml down || {
    log_warn "Some containers may not have been running (this is OK)"
}

docker-compose -f docker-compose.https.yml up -d || {
    log_error "Failed to start containers"
    exit 1
}

# Step 6: Wait for services to be healthy
log_info "Step 6: Waiting for services to become healthy..."
sleep 15

# Check container status
log_info "Container status:"
docker-compose -f docker-compose.https.yml ps

# Step 7: Show recent logs
log_info "Step 7: Recent backend logs:"
docker logs --tail 50 nester-backend 2>&1 || log_warn "Could not fetch backend logs"

# Step 8: Setup CloudWatch Agent (idempotent - only runs if not installed)
log_info "Step 8: Checking CloudWatch Agent..."
if [ ! -f "/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent" ]; then
    log_info "CloudWatch Agent not found, installing..."
    if [ -f scripts/install-cloudwatch-agent.sh ]; then
        sudo bash scripts/install-cloudwatch-agent.sh || {
            log_warn "CloudWatch Agent installation failed (non-critical)"
        }
    else
        log_warn "install-cloudwatch-agent.sh not found, skipping CloudWatch setup"
    fi
else
    log_info "CloudWatch Agent already installed, skipping setup"
fi

log_info "Deployment script completed successfully"

