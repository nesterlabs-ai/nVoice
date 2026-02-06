#!/bin/bash
# Configure Docker daemon with AWS credentials for CloudWatch Logs
# This allows the awslogs driver to use IAM user credentials instead of instance role
#
# Run this script after 'aws configure' to enable CloudWatch logging
set -e

REGION="${AWS_REGION:-us-west-2}"

echo "Configuring Docker daemon for CloudWatch Logs..."

# Get credentials from AWS CLI config
AWS_KEY=$(aws configure get aws_access_key_id)
AWS_SECRET=$(aws configure get aws_secret_access_key)

if [ -z "$AWS_KEY" ] || [ -z "$AWS_SECRET" ]; then
    echo "ERROR: AWS credentials not configured."
    echo "Run 'aws configure' first with your IAM user credentials."
    exit 1
fi

# Create systemd override for Docker daemon
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo tee /etc/systemd/system/docker.service.d/aws-credentials.conf > /dev/null << EOF
[Service]
Environment="AWS_ACCESS_KEY_ID=$AWS_KEY"
Environment="AWS_SECRET_ACCESS_KEY=$AWS_SECRET"
Environment="AWS_REGION=$REGION"
EOF

# Reload systemd and restart Docker
sudo systemctl daemon-reload
sudo systemctl restart docker

echo "Docker daemon configured for CloudWatch Logs (region: $REGION)"
echo "Restart containers with: docker compose down && docker compose up -d"
