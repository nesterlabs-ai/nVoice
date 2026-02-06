"""
CloudWatch Logs for NesterAI Voice Assistant.

Creates CloudWatch Log Group for centralized logging from Docker containers
running on Lightsail. Enables viewing logs via AWS Console without SSH.
"""

from constructs import Construct
from aws_cdk import (
    RemovalPolicy,
    aws_logs as logs,
)

from utils.config_loader import NesterConfig


class NesterCloudWatchLogs(Construct):
    """
    Creates CloudWatch Log Group for container logs.

    Docker containers on Lightsail use the awslogs driver to ship
    logs directly to CloudWatch, enabling centralized log viewing
    and retention management.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        config: NesterConfig,
    ) -> None:
        super().__init__(scope, id)

        self.config = config
        prefix = config.resource_prefix

        # Create log group for container logs
        self.log_group = logs.LogGroup(
            self,
            "ContainerLogs",
            log_group_name=f"/nester-ai/{config.environment}",
            retention=logs.RetentionDays.ONE_MONTH,  # 30 days
            removal_policy=RemovalPolicy.RETAIN,  # Keep logs on stack deletion
        )

    @property
    def log_group_name(self) -> str:
        """Name of the log group."""
        return self.log_group.log_group_name

    @property
    def log_group_arn(self) -> str:
        """ARN of the log group."""
        return self.log_group.log_group_arn

    @property
    def region(self) -> str:
        """AWS region for the log group."""
        return self.config.aws.region