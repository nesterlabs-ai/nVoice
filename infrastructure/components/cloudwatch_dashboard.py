"""
CloudWatch Dashboard for NesterAI Voice Assistant.

Creates a CloudWatch Dashboard with widgets for session metrics,
error tracking, and RAG performance monitoring. Also creates alarms
for critical thresholds.
"""

from constructs import Construct
from aws_cdk import (
    Duration,
    aws_cloudwatch as cloudwatch,
)

from utils.config_loader import NesterConfig


class NesterCloudWatchDashboard(Construct):
    """
    Creates a CloudWatch Dashboard for voice assistant monitoring.

    Metrics are emitted by the application via boto3 PutMetricData
    to the 'NesterVoiceAI' namespace. This component creates:
    - Dashboard with session, error, and RAG performance widgets
    - Alarms for high error rate and high RAG latency
    """

    NAMESPACE = "NesterVoiceAI"

    def __init__(
        self,
        scope: Construct,
        id: str,
        config: NesterConfig,
    ) -> None:
        super().__init__(scope, id)

        self.config = config
        prefix = config.resource_prefix
        env = config.environment

        # --- Metrics ---
        session_start_metric = cloudwatch.Metric(
            namespace=self.NAMESPACE,
            metric_name="SessionStart",
            dimensions_map={"Environment": env},
            statistic="Sum",
            period=Duration.hours(1),
        )

        active_sessions_metric = cloudwatch.Metric(
            namespace=self.NAMESPACE,
            metric_name="ActiveSessions",
            dimensions_map={"Environment": env},
            statistic="Maximum",
            period=Duration.minutes(5),
        )

        session_duration_metric = cloudwatch.Metric(
            namespace=self.NAMESPACE,
            metric_name="SessionDuration",
            dimensions_map={"Environment": env},
            statistic="Average",
            period=Duration.hours(1),
        )

        error_metric = cloudwatch.Metric(
            namespace=self.NAMESPACE,
            metric_name="Error",
            dimensions_map={"Environment": env},
            statistic="Sum",
            period=Duration.hours(1),
        )

        rag_latency_metric = cloudwatch.Metric(
            namespace=self.NAMESPACE,
            metric_name="RAGLatency",
            dimensions_map={"Environment": env},
            statistic="p90",
            period=Duration.hours(1),
        )

        rag_calls_metric = cloudwatch.Metric(
            namespace=self.NAMESPACE,
            metric_name="RAGCall",
            dimensions_map={"Environment": env},
            statistic="Sum",
            period=Duration.hours(1),
        )

        rag_errors_metric = cloudwatch.Metric(
            namespace=self.NAMESPACE,
            metric_name="RAGError",
            dimensions_map={"Environment": env},
            statistic="Sum",
            period=Duration.hours(1),
        )

        # --- Dashboard ---
        self.dashboard = cloudwatch.Dashboard(
            self,
            "Dashboard",
            dashboard_name=f"{prefix}-voice-assistant",
            default_interval=Duration.hours(24),
        )

        # Row 1: Session overview
        self.dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Sessions per Hour",
                left=[session_start_metric],
                width=8,
                height=6,
            ),
            cloudwatch.GraphWidget(
                title="Active Sessions (5m)",
                left=[active_sessions_metric],
                width=8,
                height=6,
            ),
            cloudwatch.SingleValueWidget(
                title="Total Sessions (24h)",
                metrics=[session_start_metric],
                width=8,
                height=6,
            ),
        )

        # Row 2: Session quality
        self.dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Avg Session Duration (sec)",
                left=[session_duration_metric],
                width=12,
                height=6,
            ),
            cloudwatch.GraphWidget(
                title="Errors per Hour",
                left=[error_metric],
                width=12,
                height=6,
            ),
        )

        # Row 3: RAG performance
        self.dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="RAG Latency p90 (ms)",
                left=[rag_latency_metric],
                width=12,
                height=6,
            ),
            cloudwatch.GraphWidget(
                title="RAG Calls & Errors",
                left=[rag_calls_metric],
                right=[rag_errors_metric],
                width=12,
                height=6,
            ),
        )

        # --- Alarms ---
        self.high_error_alarm = cloudwatch.Alarm(
            self,
            "HighErrorRate",
            alarm_name=f"{prefix}-high-error-rate",
            alarm_description="More than 10 errors per hour in NesterVoiceAI",
            metric=error_metric,
            threshold=10,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        )

        self.high_rag_latency_alarm = cloudwatch.Alarm(
            self,
            "HighRAGLatency",
            alarm_name=f"{prefix}-high-rag-latency",
            alarm_description="RAG p90 latency exceeds 5 seconds",
            metric=rag_latency_metric,
            threshold=5000,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        )
