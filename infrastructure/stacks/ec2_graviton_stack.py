"""
EC2 Graviton Infrastructure Stack for NesterAI Voice Assistant.

Deploys an EC2 Graviton (ARM64) instance as a parallel test environment
for benchmarking emotion detection performance vs Lightsail x86.

Shares Secrets Manager with the dev environment but has its own
ECR repos (ARM64 images) and CloudWatch log group.
"""

from constructs import Construct
from aws_cdk import (
    Stack,
    CfnOutput,
    Tags,
    aws_iam as iam,
)

from utils.config_loader import NesterConfig
from components import NesterECR, NesterCloudWatchLogs, NesterSSMConfig
from components.ec2_graviton import EC2GravitonInstance


class EC2GravitonStack(Stack):
    """
    EC2 Graviton infrastructure stack for NesterAI Voice Assistant.

    Creates:
    - ECR repositories for ARM64 container images
    - CloudWatch Log Group for container logs
    - EC2 Graviton instance with IAM role, security group, and Elastic IP
    - Imports shared Secrets Manager secret from dev environment
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        config: NesterConfig,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        self.config = config

        # Apply tags to all resources in this stack
        for key, value in config.tags.items():
            Tags.of(self).add(key, value)
        Tags.of(self).add("Environment", config.environment)
        Tags.of(self).add("Stack", id)

        # 1. Create ECR repositories for ARM64 container images
        # Repo names: nester-ai-graviton-test-backend/frontend
        self.ecr = NesterECR(
            self,
            "ECR",
            config=config,
        )

        # 2. Grant the existing CI/CD IAM user push access to Graviton ECR repos
        # The CI/CD user (nester-ai-dev-ecr-user) is shared across deployments
        cicd_user = iam.User.from_user_name(
            self, "CiCdUser", "nester-ai-dev-ecr-user"
        )
        self.ecr.backend_repo.grant_pull_push(cicd_user)
        self.ecr.frontend_repo.grant_pull_push(cicd_user)

        # 3. Reference shared Secrets Manager secret (same API keys as dev) (same API keys as dev)
        # Full ARN from config avoids the partial-ARN matching issue with from_secret_name_v2
        shared_secret_arn = config.secrets.shared_secret_arn

        # 4. Create CloudWatch Log Group for container logs
        self.cloudwatch_logs = NesterCloudWatchLogs(
            self,
            "CloudWatchLogs",
            config=config,
        )

        # 5. Create SSM Parameter Store with server config
        self.ssm_config = NesterSSMConfig(
            self,
            "SSMConfig",
            config=config,
        )

        # 6. Create EC2 Graviton instance
        self.ec2_instance = EC2GravitonInstance(
            self,
            "EC2Graviton",
            config=config,
            api_keys_secret_arn=shared_secret_arn,
            ssm_parameter_name=self.ssm_config.parameter_name,
            backend_image_uri=self.ecr.backend_image_uri(config.image_tag),
            frontend_image_uri=self.ecr.frontend_image_uri(config.image_tag),
            log_group_name=self.cloudwatch_logs.log_group_name,
            log_group_arn=self.cloudwatch_logs.log_group_arn,
        )

        # Stack outputs
        CfnOutput(
            self,
            "InstanceId",
            value=self.ec2_instance.instance.instance_id,
            description="EC2 instance ID",
        )

        if config.ec2.elastic_ip.enabled:
            CfnOutput(
                self,
                "ElasticIpAddress",
                value=self.ec2_instance.ip_address,
                description="Elastic IP address of the EC2 instance",
                export_name=f"{config.resource_prefix}-elastic-ip",
            )

            CfnOutput(
                self,
                "SshCommand",
                value=f"ssh -i ~/.ssh/{config.ec2.instance.key_pair_name}.pem ec2-user@<ELASTIC_IP>",
                description="SSH command to connect to the instance (replace <ELASTIC_IP>)",
            )

        CfnOutput(
            self,
            "SharedSecretArn",
            value=shared_secret_arn,
            description="Shared Secrets Manager secret ARN (from dev environment)",
        )

        # ECR outputs
        CfnOutput(
            self,
            "BackendEcrRepoUri",
            value=self.ecr.backend_repo_uri,
            description="ECR repository URI for ARM64 backend image",
            export_name=f"{config.resource_prefix}-backend-ecr-uri",
        )

        CfnOutput(
            self,
            "FrontendEcrRepoUri",
            value=self.ecr.frontend_repo_uri,
            description="ECR repository URI for ARM64 frontend image",
            export_name=f"{config.resource_prefix}-frontend-ecr-uri",
        )

        CfnOutput(
            self,
            "EcrLoginCommand",
            value=f"aws ecr get-login-password --region {config.aws.region} | docker login --username AWS --password-stdin {self.ecr.backend_repo_uri.split('/')[0]}",
            description="Command to authenticate Docker with ECR",
        )

        # CloudWatch Logs outputs
        CfnOutput(
            self,
            "CloudWatchLogGroup",
            value=self.cloudwatch_logs.log_group_name,
            description="CloudWatch Log Group for container logs",
            export_name=f"{config.resource_prefix}-log-group",
        )

        CfnOutput(
            self,
            "CloudWatchLogsUrl",
            value=f"https://{config.aws.region}.console.aws.amazon.com/cloudwatch/home?region={config.aws.region}#logsV2:log-groups/log-group/{self.cloudwatch_logs.log_group_name.replace('/', '$252F')}",
            description="URL to view logs in CloudWatch Console",
        )

        # SSM Parameter Store output
        CfnOutput(
            self,
            "SSMParameterName",
            value=self.ssm_config.parameter_name,
            description="SSM Parameter Store path for server config",
        )