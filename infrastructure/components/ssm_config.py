"""
SSM Parameter Store construct for NesterAI server configuration.

Stores non-secret, environment-specific config (PUBLIC_URL, DOMAIN, ports, etc.)
in SSM Parameter Store. Used by refresh-env.sh on instances to build .env files.

Secrets (API keys) stay in Secrets Manager. This handles everything else.
"""

import json
from constructs import Construct
from aws_cdk import (
    aws_ssm as ssm,
    RemovalPolicy,
)

from utils.config_loader import NesterConfig


class NesterSSMConfig(Construct):
    """
    Creates an SSM Parameter with JSON server config for the environment.

    Parameter path: /nester-ai/{environment}/server-config
    Value: JSON object with all non-secret environment variables.

    refresh-env.sh reads this parameter + Secrets Manager to build .env
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        config: NesterConfig,
    ) -> None:
        super().__init__(scope, id)

        self.config = config
        app = config.application
        region = config.aws.region

        # Build server config dict
        server_config = {
            "FASTAPI_HOST": app.server.fastapi_host,
            "FASTAPI_PORT": str(app.server.fastapi_port),
            "WEBSOCKET_HOST": app.server.websocket_host,
            "WEBSOCKET_PORT": str(app.server.websocket_port),
            "SESSION_TIMEOUT": str(app.server.session_timeout),
            "LOG_LEVEL": app.server.log_level,
            "AWS_REGION": region,
            "CLOUDWATCH_LOG_GROUP": f"/nester-ai/{config.environment}",
        }

        if app.domain.name:
            server_config["DOMAIN"] = app.domain.name
            server_config["PUBLIC_URL"] = (
                f"https://{app.domain.name}"
                if app.domain.use_https
                else f"http://{app.domain.name}"
            )

        # Add Graviton optimizations if present
        if config.graviton.optimizations:
            for k, v in config.graviton.optimizations.items():
                server_config[k] = v

        self.parameter_name = f"/nester-ai/{config.environment}/server-config"

        self.parameter = ssm.StringParameter(
            self,
            "ServerConfig",
            parameter_name=self.parameter_name,
            string_value=json.dumps(server_config),
            description=f"Server configuration for NesterAI ({config.environment})",
            tier=ssm.ParameterTier.STANDARD,
        )

    @property
    def parameter_arn(self) -> str:
        return self.parameter.parameter_arn