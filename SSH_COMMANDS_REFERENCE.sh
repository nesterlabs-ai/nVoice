#!/bin/bash
# =============================================================================
# SSH COMMANDS REFERENCE - Nester Voice Bot Deployment
# =============================================================================
# Server: 3.6.64.48 (AWS Lightsail - ap-south-1)
# User: ec2-user
# Application: NesterConversationalBot (Voice AI Assistant)
#
# IMPORTANT: This file contains the SSH private key inline. Keep it secure!
# =============================================================================

# SSH Private Key (embedded for easy use)
SSH_KEY='-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAzCUBJtu9zIaWp5q2PRlLjqxXJpqb2kUc+bDqf3jxg4iCoHed
dARdnL0Ojx4FGQUQkhu+vvCV8sDAF2SZ1p51MM9Q7R5wzMAGMQr+ntnJnk4OSQTb
RSgK5OTgF9C/XZU4mqkpgRFR8dhJYtoqyDoeslr1r6Ze7cKCWj9Miu2RJatVLK1Z
nuJG2I2UNDWbUx1QaMo3QmeP3BiIRIenlu18oTfydMjEugOiR0g9tza2HzaE5a7J
HDOqxkxJ6qmubCZ5GCasWBs5gr6rHq0wR/FLA2CbFCnotelnKyvhKY2xi62f1CUl
ijZF5A9dvv/2itwkShRdmPqhBByiRjRWXEihrwIDAQABAoIBAENQaGLRznHkZ0T4
5OKctqdi+JHIJWABrh4/UfOag7iliL008/xPfDa0uFpEwdWQL/idoXYAitEy8aRF
Dd0Q/v+LPNoTUYqSPvho8bCbi7nhbyBws4TIQV9cgPAZayCGldWZtg/TEDw432nz
GmxPjdOt3pl+uIqZurXbbXfaAiRzFSIWGORPiFjI7VBYGM3x1UMSOjMQIWSQl8qX
3h1iwY0HWfTO2xaLQKjbvuJ1L1lAj9wBm9BEeInZ+1sWVHcFTlhO6HZy71zAFK77
tpM1M1XjsAtLsbFMQwo7yNW3Ta+zYO5/jLK6Xk061jijC1whH3RLmHbXMZwrAF13
ckJ/wbECgYEA+OOfWjEqWfhllLMbASerQfpt+nFHg7pJCMHA2WqozP3acI0rHE+x
WhpBl0ksmh916v+RkUqXlgjDgOn2G8JuLaoPuJdC48zyAaYpYJgkMWZgQjPTUT8I
j+4r8N1H04L3UbbT47bGXT7h8iqsPxE93R90sCAG8J1Gd1fogLg2CmsCgYEA0foe
nlS3tEspRru6CmzmqGAytnzMgFxCvD62Hga6i91auUXVDX7h9tBPvsiXoNzaoFYp
0yBKNovMDuhHKQZWZ15LortU7+f8vcNI0lRTgKPcMV5vICjh4RatyIYU4LkdmRRt
S49zNquPnAN6dFDifosWjwu7gh0Y+ZLF/11NXs0CgYBXpZkNYvj+HApxti0RWA3o
Oy+VnWTIz8Y+bjTim7v8DH1rW1tOKgZTq6FjjGJHmEKnUf7KQpFlRYrLkBiaJ/sy
24uTvrjQjfC/getaV9mPB/Vn+uY021TBkucoeFR9+MXtocu2ijwKxEU/SaXEw+ac
QyKNj4nCHDCfgHahNb3aJwKBgQC0+mWFhfNIHDgZVRhGgBJWMYPEMdB5GgwS/+Is
AxSqFEFryrqVBTVxa54wC+hUp8Zvx5QI+p28YcWhW6Zpv6KdOXLrcZcFp+f5DuYn
ErNd/t18V65kA5icTtW+LYK1JhhSpn6FT8C38Cq5B2517nkpJGxvImec/8NU6KJr
NVnISQKBgQCgZUiiLlZ9TG96UiIhqNRI38shJVlHuWb60pQjSyxis8fzKs+spUEH
7/3suR+nKiZ/3HBFW2r7HO81y1dRe/CaMcbBKzBDGVMepiffCxnQNsNyW8FfrD3o
puEGSczGyovEcJkoJcPtASe2uYttWcPxFQYF5mZc3KFZNL9hTVLTRw==
-----END RSA PRIVATE KEY-----'

# Server configuration
SERVER="ec2-user@3.6.64.48"
DEPLOY_DIR="/home/ec2-user/nester-bot"

# =============================================================================
# HELPER FUNCTION: Execute SSH command with embedded key
# =============================================================================
ssh_exec() {
    echo "$SSH_KEY" | ssh -i /dev/stdin -o StrictHostKeyChecking=no "$SERVER" "$@"
}

# =============================================================================
# 1. BASIC SERVER ACCESS
# =============================================================================

# Connect to server interactively
# Usage: Copy the command below and run it in your terminal
echo "$SSH_KEY" > /tmp/voice-key.pem && chmod 600 /tmp/voice-key.pem
ssh -i /tmp/voice-key.pem -o StrictHostKeyChecking=no ec2-user@3.6.64.48

# =============================================================================
# 2. CHECK SERVER STATUS & CONTAINERS
# =============================================================================

# Check all running Docker containers with their status and ports
ssh_exec "sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"

# Check backend container logs (last 50 lines)
ssh_exec "sudo docker logs nester-backend --tail 50"

# Check backend logs for errors only
ssh_exec "sudo docker logs nester-backend --tail 100 | grep -i 'error\|exception\|warning'"

# Check if backend is running and healthy
ssh_exec "sudo docker ps | grep nester-backend"

# Check current git commit on server
ssh_exec "cd $DEPLOY_DIR && git log -1 --oneline"

# Check server disk usage
ssh_exec "df -h"

# Check server memory usage
ssh_exec "free -h"

# =============================================================================
# 3. ENVIRONMENT VARIABLES & SECRETS
# =============================================================================

# Check if API keys are set in .env file
ssh_exec "grep -E 'GOOGLE_API_KEY|LIGHTRAG_API_KEY|DEEPGRAM_API_KEY' $DEPLOY_DIR/.env"

# Fetch secrets from AWS Parameter Store and update .env
ssh_exec "cd $DEPLOY_DIR && bash scripts/fetch-secrets.sh"

# Add LIGHTRAG_API_KEY to .env (if missing)
ssh_exec "echo 'LIGHTRAG_API_KEY=805c5c51f72690e3d60a94feba3e9958bef824f28332f25f3f5638ef6f6d642f' >> $DEPLOY_DIR/.env"

# Verify API keys inside running container
ssh_exec "sudo docker exec nester-backend printenv | grep -E 'GOOGLE_API_KEY|LIGHTRAG_API_KEY'"

# Check current GOOGLE_API_KEY value
ssh_exec "sudo docker exec nester-backend printenv | grep GOOGLE_API_KEY"

# =============================================================================
# 4. CODE DEPLOYMENT
# =============================================================================

# Pull latest code from GitHub
ssh_exec "cd $DEPLOY_DIR && git pull origin main"

# Check git status
ssh_exec "cd $DEPLOY_DIR && git status"

# Build new Docker image for backend
ssh_exec "cd $DEPLOY_DIR && sudo docker build -t nester-bot-backend ."

# Rebuild backend with docker-compose
ssh_exec "cd $DEPLOY_DIR && export DOMAIN=3.6.64.48.nip.io && sudo -E docker-compose -f docker-compose.https.yml build backend"

# =============================================================================
# 5. CONTAINER MANAGEMENT
# =============================================================================

# Restart backend container only
ssh_exec "cd $DEPLOY_DIR && export DOMAIN=3.6.64.48.nip.io && sudo -E docker-compose -f docker-compose.https.yml restart backend"

# Stop and remove backend, then start fresh
ssh_exec "cd $DEPLOY_DIR && export DOMAIN=3.6.64.48.nip.io && sudo -E docker-compose -f docker-compose.https.yml stop backend && sudo -E docker-compose -f docker-compose.https.yml rm -f backend && sudo -E docker-compose -f docker-compose.https.yml up -d backend"

# Force recreate backend container (picks up new .env variables)
ssh_exec "cd $DEPLOY_DIR && export DOMAIN=3.6.64.48.nip.io && sudo -E docker-compose -f docker-compose.https.yml up -d --force-recreate backend"

# Restart all services (caddy, backend, frontend)
ssh_exec "cd $DEPLOY_DIR && export DOMAIN=3.6.64.48.nip.io && sudo -E docker-compose -f docker-compose.https.yml up -d"

# Stop all containers
ssh_exec "cd $DEPLOY_DIR && sudo docker-compose -f docker-compose.https.yml down"

# Start all containers
ssh_exec "cd $DEPLOY_DIR && export DOMAIN=3.6.64.48.nip.io && sudo -E docker-compose -f docker-compose.https.yml up -d"

# View logs for all containers
ssh_exec "cd $DEPLOY_DIR && sudo docker-compose -f docker-compose.https.yml logs -f"

# =============================================================================
# 6. COMPLETE DEPLOYMENT WORKFLOW
# =============================================================================

# Full deployment: pull code, rebuild, and restart
ssh_exec "cd $DEPLOY_DIR && git pull && sudo docker build -t nester-bot-backend . && export DOMAIN=3.6.64.48.nip.io && sudo -E docker-compose -f docker-compose.https.yml stop backend && sudo -E docker-compose -f docker-compose.https.yml rm -f backend && sudo -E docker-compose -f docker-compose.https.yml up -d backend"

# =============================================================================
# 7. DEBUGGING & MONITORING
# =============================================================================

# Check backend logs in real-time
ssh_exec "sudo docker logs -f nester-backend"

# Check logs from last 2 minutes
ssh_exec "sudo docker logs nester-backend --since 2m"

# Check for specific errors in logs
ssh_exec "sudo docker logs nester-backend | grep -i 'quota\|403\|429\|error'"

# Check LightRAG related logs
ssh_exec "sudo docker logs nester-backend --since 10m | grep -E 'lightrag|rag|LightRAG' -i"

# Check greeting-related logs
ssh_exec "sudo docker logs nester-backend --since 10m | grep -E 'greeting|Client connected|Hey there'"

# Check if greeting fix is deployed in running container
ssh_exec "sudo docker exec nester-backend grep -n '_greeting_sent' /app/app/core/voice_assistant.py | head -5"

# Check container resource usage
ssh_exec "sudo docker stats --no-stream"

# Check network connectivity from container
ssh_exec "sudo docker exec nester-backend ping -c 3 16.170.172.18"

# =============================================================================
# 8. AWS PARAMETER STORE MANAGEMENT
# =============================================================================

# Note: These commands run locally, not via SSH

# Update GOOGLE_API_KEY in Parameter Store
aws ssm put-parameter --name "/nester/GOOGLE_API_KEY" --value "AIzaSyAPF-F2IZ7fMJylNzGrwA_DrIBOvN29zg0" --type "SecureString" --overwrite --region ap-south-1

# Add LIGHTRAG_API_KEY to Parameter Store
aws ssm put-parameter --name "/nester/LIGHTRAG_API_KEY" --value "805c5c51f72690e3d60a94feba3e9958bef824f28332f25f3f5638ef6f6d642f" --type "SecureString" --region ap-south-1

# List all parameters
aws ssm describe-parameters --region ap-south-1 --query 'Parameters[*].[Name,Type]' --output table | grep -i "nester"

# Get a specific parameter value
aws ssm get-parameter --name "/nester/GOOGLE_API_KEY" --with-decryption --region ap-south-1 --query "Parameter.Value" --output text

# =============================================================================
# 9. FIREWALL & NETWORKING
# =============================================================================

# Note: These commands run locally, not via SSH

# Open required ports on Lightsail firewall
aws lightsail put-instance-public-ports \
    --instance-name nester-voice-bot \
    --port-infos \
        fromPort=22,toPort=22,protocol=tcp,cidrs=0.0.0.0/0 \
        fromPort=80,toPort=80,protocol=tcp,cidrs=0.0.0.0/0 \
        fromPort=443,toPort=443,protocol=tcp,cidrs=0.0.0.0/0 \
        fromPort=8765,toPort=8765,protocol=tcp,cidrs=0.0.0.0/0 \
    --region ap-south-1

# =============================================================================
# 10. DOCKER COMPOSE CONFIGURATION MANAGEMENT
# =============================================================================

# Add LIGHTRAG_API_KEY to docker-compose environment variables
ssh_exec "cd $DEPLOY_DIR && sudo sed -i '/GOOGLE_API_KEY=\${GOOGLE_API_KEY}/a\      - LIGHTRAG_API_KEY=\${LIGHTRAG_API_KEY}' docker-compose.https.yml"

# View docker-compose configuration
ssh_exec "cat $DEPLOY_DIR/docker-compose.https.yml"

# Check docker-compose environment variables
ssh_exec "cd $DEPLOY_DIR && docker-compose -f docker-compose.https.yml config"

# =============================================================================
# 11. FILE MANAGEMENT
# =============================================================================

# Check if file exists
ssh_exec "ls -la $DEPLOY_DIR/.env"

# View file contents
ssh_exec "cat $DEPLOY_DIR/app/config/config.yaml"

# Edit file (add line to .env)
ssh_exec "echo 'NEW_VAR=value' >> $DEPLOY_DIR/.env"

# Search for text in files
ssh_exec "grep -r 'LightRAG' $DEPLOY_DIR/app/ --include='*.py'"

# Check file inside container
ssh_exec "sudo docker exec nester-backend cat /app/app/config/config.yaml"

# =============================================================================
# 12. HEALTH CHECKS
# =============================================================================

# Check if backend is responding
ssh_exec "curl -s http://localhost:7860/health"

# Check if frontend is accessible
ssh_exec "curl -s http://localhost/ | head -20"

# Check Caddy status
ssh_exec "sudo docker logs nester-caddy --tail 20"

# Test LightRAG API from server
ssh_exec "curl -s http://16.170.172.18/health"

# =============================================================================
# 13. CLEANUP COMMANDS
# =============================================================================

# Remove stopped containers
ssh_exec "sudo docker container prune -f"

# Remove unused images
ssh_exec "sudo docker image prune -a -f"

# Remove unused volumes
ssh_exec "sudo docker volume prune -f"

# Clean Docker system (free up space)
ssh_exec "sudo docker system prune -a -f"

# =============================================================================
# 14. QUICK TROUBLESHOOTING
# =============================================================================

# If bot not responding - check quota error
ssh_exec "sudo docker logs nester-backend --tail 50 | grep -i '429\|quota'"

# If RAG not working - check 403 error
ssh_exec "sudo docker logs nester-backend --tail 50 | grep -i '403\|lightrag'"

# If greeting duplicates - check greeting logs
ssh_exec "sudo docker logs nester-backend --since 5m | grep -i 'greeting\|tts.*hey there'"

# If container won't start - check startup errors
ssh_exec "sudo docker logs nester-backend --tail 100 | grep -i 'error\|failed\|exception'"

# =============================================================================
# 15. USEFUL ONE-LINERS
# =============================================================================

# Complete redeploy in one command
ssh_exec "cd $DEPLOY_DIR && git pull && bash scripts/fetch-secrets.sh && echo 'LIGHTRAG_API_KEY=805c5c51f72690e3d60a94feba3e9958bef824f28332f25f3f5638ef6f6d642f' >> .env && sudo docker build -t nester-bot-backend . && export DOMAIN=3.6.64.48.nip.io && sudo -E docker-compose -f docker-compose.https.yml up -d --force-recreate backend"

# Quick status check
ssh_exec "echo '=== Docker Containers ===' && sudo docker ps && echo -e '\n=== Current Commit ===' && cd $DEPLOY_DIR && git log -1 --oneline && echo -e '\n=== Recent Logs ===' && sudo docker logs nester-backend --tail 10"

# =============================================================================
# 16. APPLICATION URLs
# =============================================================================

# Frontend: https://3.6.64.48.nip.io/
# Backend API: https://3.6.64.48.nip.io/health
# WebSocket: wss://3.6.64.48.nip.io/ws
# LightRAG API: http://16.170.172.18/

# =============================================================================
# 17. IMPORTANT NOTES
# =============================================================================

# 1. GitHub Actions auto-deploys on push to main branch
# 2. All secrets are stored in AWS Parameter Store (region: ap-south-1)
# 3. docker-compose.https.yml uses Caddy for automatic HTTPS
# 4. Domain: 3.6.64.48.nip.io (nip.io provides free wildcard DNS)
# 5. Gemini API Key: AIzaSyAPF-F2IZ7fMJylNzGrwA_DrIBOvN29zg0
# 6. LightRAG API Key: 805c5c51f72690e3d60a94feba3e9958bef824f28332f25f3f5638ef6f6d642f

# =============================================================================
# END OF SSH COMMANDS REFERENCE
# =============================================================================
