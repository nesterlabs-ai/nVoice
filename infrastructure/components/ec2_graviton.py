"""
EC2 Graviton instance construct for NesterAI Voice Assistant.

Uses native CDK L2 constructs for EC2, IAM, and VPC.
Eliminates all Lightsail workarounds (no custom resources, no credential hacks).
The IAM instance role provides automatic ECR, Secrets Manager, and CloudWatch access.
"""

from constructs import Construct
from aws_cdk import (
    CfnOutput,
    aws_ec2 as ec2,
    aws_iam as iam,
)

from utils.config_loader import NesterConfig


class EC2GravitonInstance(Construct):
    """
    Creates EC2 Graviton (ARM64) instance with:
    - IAM instance role (ECR pull, Secrets read, CloudWatch write)
    - Security group (configurable ports)
    - Elastic IP for stable endpoint
    - User data script for Docker + app setup (fully automated, no manual SSH needed)
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        config: NesterConfig,
        api_keys_secret_arn: str,
        backend_image_uri: str,
        frontend_image_uri: str,
        log_group_name: str,
        log_group_arn: str,
    ) -> None:
        super().__init__(scope, id)

        self.config = config
        self.api_keys_secret_arn = api_keys_secret_arn
        self.backend_image_uri = backend_image_uri
        self.frontend_image_uri = frontend_image_uri
        self.log_group_name = log_group_name

        prefix = config.resource_prefix
        region = config.aws.region

        # Use default VPC
        vpc = ec2.Vpc.from_lookup(self, "DefaultVpc", is_default=True)

        # Security Group
        self.security_group = ec2.SecurityGroup(
            self,
            "SecurityGroup",
            vpc=vpc,
            security_group_name=f"{prefix}-sg",
            description=f"Security group for {prefix} EC2 instance",
            allow_all_outbound=True,
        )

        for port_config in config.ec2.networking.ports:
            cidrs = port_config.cidrs if port_config.cidrs else ["0.0.0.0/0"]
            for cidr in cidrs:
                self.security_group.add_ingress_rule(
                    peer=ec2.Peer.ipv4(cidr),
                    connection=ec2.Port.tcp(port_config.port),
                    description=f"Allow port {port_config.port} from {cidr}",
                )

        # IAM Role with instance profile
        self.instance_role = iam.Role(
            self,
            "InstanceRole",
            role_name=f"{prefix}-ec2-role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMManagedInstanceCore"
                ),
            ],
        )

        # ECR pull permissions
        self.instance_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ecr:GetAuthorizationToken"],
                resources=["*"],
            )
        )
        self.instance_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                ],
                resources=[
                    f"arn:aws:ecr:{region}:*:repository/{prefix}-backend",
                    f"arn:aws:ecr:{region}:*:repository/{prefix}-frontend",
                ],
            )
        )

        # Secrets Manager read permissions (shared dev secret)
        self.instance_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret",
                ],
                resources=[api_keys_secret_arn],
            )
        )

        # CloudWatch Logs write permissions
        self.instance_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogStreams",
                ],
                resources=[f"{log_group_arn}:*"],
            )
        )

        # AMI - Amazon Linux 2023 ARM64
        ami = ec2.MachineImage.latest_amazon_linux2023(
            cpu_type=ec2.AmazonLinuxCpuType.ARM_64,
        )

        # User data script
        user_data = ec2.UserData.for_linux()
        user_data.add_commands(self._generate_user_data())

        # EC2 Instance
        self.instance = ec2.Instance(
            self,
            "Instance",
            instance_name=f"{prefix}-instance",
            instance_type=ec2.InstanceType(config.ec2.instance.instance_type),
            machine_image=ami,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=self.security_group,
            role=self.instance_role,
            user_data=user_data,
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/xvda",
                    volume=ec2.BlockDeviceVolume.ebs(
                        config.ec2.instance.volume_size_gb,
                        volume_type=ec2.EbsDeviceVolumeType.GP3,
                    ),
                )
            ],
            key_pair=ec2.KeyPair.from_key_pair_name(
                self,
                "KeyPair",
                config.ec2.instance.key_pair_name,
            ) if config.ec2.instance.key_pair_name else None,
        )

        # Elastic IP
        if config.ec2.elastic_ip.enabled:
            self.eip = ec2.CfnEIP(
                self,
                "ElasticIp",
                tags=[
                    {"key": "Name", "value": f"{prefix}-eip"},
                    {"key": "Environment", "value": config.environment},
                ],
            )

            ec2.CfnEIPAssociation(
                self,
                "EipAssociation",
                eip=self.eip.ref,
                instance_id=self.instance.instance_id,
            )

            self.ip_address = self.eip.attr_public_ip
        else:
            self.ip_address = self.instance.instance_public_ip

    def _generate_user_data(self) -> str:
        """
        Generate the user data script for EC2 instance initialization.

        Key difference from Lightsail: IAM instance role handles all AWS auth
        automatically - no manual `aws configure` or credential hacks needed.
        """
        config = self.config
        app = config.application
        region = config.aws.region
        use_https = app.domain.use_https and app.domain.name

        # ECR registry URL from image URI
        ecr_registry = self.backend_image_uri.split("/")[0]

        # Environment variables for .env file
        env_vars = {
            "FASTAPI_HOST": app.server.fastapi_host,
            "FASTAPI_PORT": str(app.server.fastapi_port),
            "WEBSOCKET_HOST": app.server.websocket_host,
            "WEBSOCKET_PORT": str(app.server.websocket_port),
            "SESSION_TIMEOUT": str(app.server.session_timeout),
            "LOG_LEVEL": app.server.log_level,
            "AWS_REGION": region,
            "CLOUDWATCH_LOG_GROUP": self.log_group_name,
        }

        if app.domain.name:
            env_vars["DOMAIN"] = app.domain.name
            env_vars["PUBLIC_URL"] = (
                f"https://{app.domain.name}"
                if app.domain.use_https
                else f"http://{app.domain.name}"
            )

        # Graviton optimization env vars for docker-compose
        graviton_env_lines = ""
        if config.graviton.optimizations:
            graviton_env_lines = "\n".join(
                f"      - {k}={v}"
                for k, v in config.graviton.optimizations.items()
            )

        # Docker compose content
        if use_https:
            docker_compose = self._generate_https_compose(app, graviton_env_lines)
            caddyfile_section = self._generate_caddyfile(app)
        else:
            docker_compose = self._generate_http_compose(app, graviton_env_lines)
            caddyfile_section = ""

        env_file_content = "\n".join(f"{k}={v}" for k, v in env_vars.items())

        return f"""
set -e

# Log all output
exec > >(tee /var/log/user-data.log) 2>&1
echo "Starting NesterAI Graviton instance setup..."

# Update system
yum update -y

# Install Docker
yum install -y docker jq
systemctl enable docker
systemctl start docker

# Install Docker Compose v2
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Add ec2-user to docker group
usermod -aG docker ec2-user

# Create swap space (t4g.small has 2GB RAM)
if [ ! -f /swapfile ]; then
    dd if=/dev/zero of=/swapfile bs=1M count=1024
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile swap swap defaults 0 0' >> /etc/fstab
fi

# Install AWS CLI v2
if ! command -v aws &> /dev/null; then
    curl "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o "awscliv2.zip"
    unzip -q awscliv2.zip
    ./aws/install
    rm -rf aws awscliv2.zip
fi

# Create application directory
mkdir -p /opt/nester
cd /opt/nester

# Configuration
REGION="{region}"
API_KEYS_SECRET_ARN="{self.api_keys_secret_arn}"
ECR_REGISTRY="{ecr_registry}"
BACKEND_IMAGE="{self.backend_image_uri}"
FRONTEND_IMAGE="{self.frontend_image_uri}"

# ============================================
# EC2 Instance Role - No manual setup needed!
# IAM instance role provides automatic access to:
# - ECR (docker pull)
# - Secrets Manager (API keys)
# - CloudWatch Logs (container logging)
# ============================================

# Create .env with server configuration
cat > /opt/nester/.env << 'ENVEOF'
# Auto-generated environment file
# Server Configuration
{env_file_content}

# API Keys - populated automatically from Secrets Manager
ENVEOF
chown ec2-user:ec2-user /opt/nester/.env
chmod 644 /opt/nester/.env

# ============================================
# ECR login script (uses instance role - no aws configure needed)
# ============================================
cat > /opt/nester/ecr-login.sh << 'ECREOF'
#!/bin/bash
aws ecr get-login-password --region {region} | docker login --username AWS --password-stdin {ecr_registry}
ECREOF
chmod +x /opt/nester/ecr-login.sh

{caddyfile_section}

# ============================================
# Docker Compose
# ============================================
cat > /opt/nester/docker-compose.yml << 'COMPOSEEOF'
{docker_compose}
COMPOSEEOF

# ============================================
# Setup secrets script (fetches from Secrets Manager via instance role)
# ============================================
cat > /opt/nester/setup-secrets.sh << 'SETUPEOF'
#!/bin/bash
set -e
cd /opt/nester
REGION="{region}"
API_KEYS_SECRET_ARN="{self.api_keys_secret_arn}"

echo "Fetching API keys from Secrets Manager..."
SECRET_JSON=$(aws secretsmanager get-secret-value --secret-id "$API_KEYS_SECRET_ARN" --region "$REGION" --query SecretString --output text)

if [ -z "$SECRET_JSON" ] || [ "$SECRET_JSON" == "null" ]; then
    echo "ERROR: Could not fetch secrets"
    exit 1
fi

# Append secrets to .env (skip placeholders)
echo "" >> .env
echo "# API Keys from Secrets Manager" >> .env
echo "$SECRET_JSON" | python3 -c "
import sys, json
try:
    secrets = json.load(sys.stdin)
    for key, value in secrets.items():
        if not str(value).startswith('PLACEHOLDER_'):
            print(f'{{key}}={{value}}')
except Exception as e:
    print(f'Error: {{e}}', file=sys.stderr)
    sys.exit(1)
" >> .env

echo "Secrets configured successfully!"
echo "Run './deploy.sh' to start the service"
SETUPEOF
chmod +x /opt/nester/setup-secrets.sh
chown ec2-user:ec2-user /opt/nester/setup-secrets.sh

# ============================================
# Deploy script
# ============================================
cat > /opt/nester/deploy.sh << 'DEPLOYEOF'
#!/bin/bash
set -e
cd /opt/nester

echo "Logging into ECR..."
./ecr-login.sh

echo "Pulling latest images..."
docker compose pull

echo "Starting containers..."
docker compose up -d --force-recreate

echo ""
echo "Deployment complete!"
docker compose ps
DEPLOYEOF
chmod +x /opt/nester/deploy.sh
chown ec2-user:ec2-user /opt/nester/deploy.sh

# ============================================
# Refresh env script
# ============================================
cat > /opt/nester/refresh-env.sh << 'REFRESHEOF'
#!/bin/bash
set -e
cd /opt/nester
REGION="{region}"
API_KEYS_SECRET_ARN="{self.api_keys_secret_arn}"

echo "Fetching latest secrets..."
SECRET_JSON=$(aws secretsmanager get-secret-value --secret-id "$API_KEYS_SECRET_ARN" --region "$REGION" --query SecretString --output text)

# Backup old .env
cp .env .env.backup

# Recreate .env with server config
cat > .env << 'ENVEOF'
# Auto-generated environment file
# Server Configuration
{env_file_content}
ENVEOF

# Append secrets
echo "" >> .env
echo "# API Keys from Secrets Manager" >> .env
echo "$SECRET_JSON" | python3 -c "
import sys, json
try:
    secrets = json.load(sys.stdin)
    for key, value in secrets.items():
        if not str(value).startswith('PLACEHOLDER_'):
            print(f'{{key}}={{value}}')
except:
    pass
" >> .env

echo "Environment refreshed. Restart containers with: docker compose up -d --force-recreate"
REFRESHEOF
chmod +x /opt/nester/refresh-env.sh
chown ec2-user:ec2-user /opt/nester/refresh-env.sh

# ============================================
# Helper scripts
# ============================================
cat > /opt/nester/logs.sh << 'LOGSEOF'
#!/bin/bash
cd /opt/nester
docker compose logs -f "$@"
LOGSEOF
chmod +x /opt/nester/logs.sh
chown ec2-user:ec2-user /opt/nester/logs.sh

cat > /opt/nester/status.sh << 'STATUSEOF'
#!/bin/bash
cd /opt/nester
echo "=== Container Status ==="
docker compose ps
echo ""
echo "=== Recent Logs ==="
docker compose logs --tail=20
STATUSEOF
chmod +x /opt/nester/status.sh
chown ec2-user:ec2-user /opt/nester/status.sh

# ============================================
# Systemd service (auto-start after reboot)
# ============================================
cat > /etc/systemd/system/nester.service << 'SERVICEEOF'
[Unit]
Description=NesterAI Voice Assistant
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/nester
ExecStartPre=/opt/nester/ecr-login.sh
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
ExecReload=/usr/bin/docker compose pull && /usr/bin/docker compose up -d

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl daemon-reload
systemctl enable nester.service

# Set ownership for all files
chown -R ec2-user:ec2-user /opt/nester

# ============================================
# AUTOMATED FIRST DEPLOYMENT
# (Unlike Lightsail, EC2 instance role allows this on boot)
# ============================================
echo "Running automated first deployment..."

# Fetch secrets
/opt/nester/setup-secrets.sh

# Deploy containers
/opt/nester/deploy.sh

echo "========================================="
echo "NesterAI Graviton instance setup complete!"
echo "Architecture: ARM64 (Graviton)"
echo "Instance type: {config.ec2.instance.instance_type}"
echo "HTTPS enabled: {'yes' if use_https else 'no'}"
echo "========================================="
echo ""
echo "Helper scripts:"
echo "  /opt/nester/deploy.sh        - Pull and restart containers"
echo "  /opt/nester/setup-secrets.sh  - Re-fetch API keys from Secrets Manager"
echo "  /opt/nester/refresh-env.sh   - Refresh full environment"
echo "  /opt/nester/logs.sh          - View container logs"
echo "  /opt/nester/status.sh        - Check container status"
"""

    def _generate_http_compose(self, app, graviton_env_lines: str) -> str:
        """Generate docker-compose for HTTP-only mode."""
        graviton_section = ""
        if graviton_env_lines:
            graviton_section = f"""    environment:
      # Graviton PyTorch optimizations
{graviton_env_lines}
"""

        return f"""services:
  backend:
    image: {self.backend_image_uri}
    container_name: nester-backend
    restart: always
    ports:
      - "{app.server.fastapi_port}:{app.server.fastapi_port}"
    env_file:
      - .env
{graviton_section}    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:{app.server.fastapi_port}/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    logging:
      driver: awslogs
      options:
        awslogs-group: {self.log_group_name}
        awslogs-region: {self.config.aws.region}
        awslogs-stream: backend
        awslogs-create-group: "true"
    networks:
      - nester-network

  frontend:
    image: {self.frontend_image_uri}
    container_name: nester-frontend
    restart: always
    ports:
      - "80:80"
    environment:
      - BACKEND_URL=http://localhost:{app.server.fastapi_port}
    depends_on:
      backend:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:80/"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: awslogs
      options:
        awslogs-group: {self.log_group_name}
        awslogs-region: {self.config.aws.region}
        awslogs-stream: frontend
        awslogs-create-group: "true"
    networks:
      - nester-network

networks:
  nester-network:
    driver: bridge"""

    def _generate_https_compose(self, app, graviton_env_lines: str) -> str:
        """Generate docker-compose with Caddy for HTTPS."""
        graviton_section = ""
        if graviton_env_lines:
            graviton_section = f"""    environment:
      # Graviton PyTorch optimizations
{graviton_env_lines}
"""

        return f"""services:
  # Caddy - Reverse Proxy with automatic HTTPS
  caddy:
    image: caddy:2-alpine
    container_name: nester-caddy
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      backend:
        condition: service_healthy
    logging:
      driver: awslogs
      options:
        awslogs-group: {self.log_group_name}
        awslogs-region: {self.config.aws.region}
        awslogs-stream: caddy
        awslogs-create-group: "true"
    networks:
      - nester-network

  backend:
    image: {self.backend_image_uri}
    container_name: nester-backend
    restart: always
    expose:
      - "{app.server.fastapi_port}"
    env_file:
      - .env
{graviton_section}    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:{app.server.fastapi_port}/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    logging:
      driver: awslogs
      options:
        awslogs-group: {self.log_group_name}
        awslogs-region: {self.config.aws.region}
        awslogs-stream: backend
        awslogs-create-group: "true"
    networks:
      - nester-network

  frontend:
    image: {self.frontend_image_uri}
    container_name: nester-frontend
    restart: always
    expose:
      - "80"
    environment:
      - BACKEND_URL=https://{app.domain.name}
    depends_on:
      backend:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:80/"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: awslogs
      options:
        awslogs-group: {self.log_group_name}
        awslogs-region: {self.config.aws.region}
        awslogs-stream: frontend
        awslogs-create-group: "true"
    networks:
      - nester-network

networks:
  nester-network:
    driver: bridge

volumes:
  caddy_data:
  caddy_config:"""

    def _generate_caddyfile(self, app) -> str:
        """Generate Caddyfile creation script for HTTPS."""
        domain = app.domain.name
        backend_port = app.server.fastapi_port

        return f"""# Create Caddyfile for HTTPS
cat > /opt/nester/Caddyfile << 'CADDYEOF'
# Automatic HTTPS with Caddy for {domain}

{domain} {{
    # API endpoints
    handle /health* {{
        reverse_proxy backend:{backend_port}
    }}

    handle /connect* {{
        reverse_proxy backend:{backend_port}
    }}

    handle /status* {{
        reverse_proxy backend:{backend_port}
    }}

    # A2UI and Graph endpoints
    handle /a2ui/* {{
        reverse_proxy backend:{backend_port}
    }}

    handle /graph/* {{
        reverse_proxy backend:{backend_port}
    }}

    # API docs
    handle /docs* {{
        reverse_proxy backend:{backend_port}
    }}

    handle /openapi.json {{
        reverse_proxy backend:{backend_port}
    }}

    # WebSocket support
    handle /ws* {{
        reverse_proxy backend:{backend_port}
    }}

    # Frontend - default handler (must be last)
    handle {{
        reverse_proxy frontend:80
    }}

    encode gzip
}}
CADDYEOF
echo "Caddyfile created for {domain}"
"""